from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import OwnedLotCreateForm
from .models import (
    CardDetails,
    Collectible,
    CollectibleValuation,
    CollectionOperation,
    OwnedLot,
    PokemonExtension,
    PokemonSeries,
    SealedProductDetails,
)
from .services import build_market_snapshot, recompute_lot_metrics


class PokeBoardV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ash", password="pikachu")
        self.other_user = User.objects.create_user(username="misty", password="staryu")

        self.series = PokemonSeries.objects.create(name="Mega Evolution", era_order=1)
        self.other_series = PokemonSeries.objects.create(name="Ecarlate et Violet", era_order=2)

        self.extension = PokemonExtension.objects.create(series=self.series, name="Equilibre parfait", code="ME03")
        self.other_extension = PokemonExtension.objects.create(
            series=self.other_series,
            name="Aventures Ensemble",
            code="EV09",
        )

        self.card = Collectible.objects.create(kind="CARD", extension=self.extension, name="Pikachu ex")
        CardDetails.objects.create(
            collectible=self.card,
            card_number="025/182",
            rarity="Ultra Rare",
            variant="Reverse",
        )

        self.sealed = Collectible.objects.create(kind="SEALED", extension=self.extension, name="ETB Equilibre parfait")
        SealedProductDetails.objects.create(collectible=self.sealed, product_type="ETB")

        self.client = Client()
        self.client.force_login(self.user)

    def _buy(self, lot: OwnedLot, quantity: str, unit_price: str, when: str, user=None, platform=""):
        CollectionOperation.objects.create(
            user=user or lot.user,
            lot=lot,
            operation_type="BUY",
            operation_date=when,
            quantity=Decimal(quantity),
            unit_price=Decimal(unit_price),
            total_price=(Decimal(quantity) * Decimal(unit_price)),
            platform=platform,
        )

    def test_fifo_realized_and_remaining_quantity_still_work(self):
        lot = OwnedLot.objects.create(
            user=self.user,
            collectible=self.card,
            language="FR",
            card_condition="NM",
            platform="Cardmarket",
        )
        self._buy(lot, "2", "10", "2026-01-01", platform="Cardmarket")
        self._buy(lot, "1", "14", "2026-01-05", platform="Cardmarket")
        sell = CollectionOperation.objects.create(
            user=self.user,
            lot=lot,
            operation_type="SELL",
            operation_date="2026-01-10",
            quantity=Decimal("2"),
            unit_price=Decimal("16"),
            total_price=Decimal("32"),
            platform="Cardmarket",
        )

        recompute_lot_metrics(lot)
        lot.refresh_from_db()
        sell.refresh_from_db()

        self.assertEqual(lot.remaining_quantity, Decimal("1"))
        self.assertEqual(lot.acquisition_total, Decimal("14"))
        self.assertEqual(lot.average_unit_cost, Decimal("14"))
        self.assertEqual(lot.realized_pnl_total, Decimal("12"))
        self.assertEqual(sell.realized_pnl, Decimal("12"))

    def test_market_snapshot_matches_exact_card_variant_only(self):
        raw_fr_lot = OwnedLot.objects.create(
            user=self.user,
            collectible=self.card,
            language="FR",
            card_condition="NM",
        )
        self._buy(raw_fr_lot, "1", "10", "2026-02-01")
        recompute_lot_metrics(raw_fr_lot)

        CollectibleValuation.objects.create(
            collectible=self.card,
            kind="CARD",
            language="EN",
            card_condition="NM",
            unit_value=Decimal("50"),
            valued_at="2026-02-10",
            source_type="MANUAL",
        )
        CollectibleValuation.objects.create(
            collectible=self.card,
            kind="CARD",
            language="FR",
            is_graded=True,
            grading_company="PSA",
            grading_grade="10",
            unit_value=Decimal("200"),
            valued_at="2026-02-11",
            source_type="MANUAL",
        )
        CollectibleValuation.objects.create(
            collectible=self.card,
            kind="CARD",
            language="FR",
            card_condition="NM",
            unit_value=Decimal("17"),
            valued_at="2026-02-12",
            source_type="MANUAL",
        )

        snapshot = build_market_snapshot(raw_fr_lot)
        self.assertEqual(snapshot.current_unit_value, Decimal("17"))
        self.assertEqual(snapshot.current_total_value, Decimal("17"))
        self.assertEqual(snapshot.unrealized_pnl, Decimal("7"))

    def test_market_snapshot_matches_sealed_condition_variant(self):
        perfect_lot = OwnedLot.objects.create(
            user=self.user,
            collectible=self.sealed,
            language="FR",
            sealed_condition="PERFECT",
        )
        defect_lot = OwnedLot.objects.create(
            user=self.user,
            collectible=self.sealed,
            language="FR",
            sealed_condition="DEFECT",
        )
        self._buy(perfect_lot, "1", "80", "2026-02-01")
        self._buy(defect_lot, "1", "70", "2026-02-01")
        recompute_lot_metrics(perfect_lot)
        recompute_lot_metrics(defect_lot)

        CollectibleValuation.objects.create(
            collectible=self.sealed,
            kind="SEALED",
            language="FR",
            sealed_condition="PERFECT",
            unit_value=Decimal("110"),
            valued_at="2026-02-12",
            source_type="MANUAL",
        )
        CollectibleValuation.objects.create(
            collectible=self.sealed,
            kind="SEALED",
            language="FR",
            sealed_condition="DEFECT",
            unit_value=Decimal("85"),
            valued_at="2026-02-12",
            source_type="MANUAL",
        )

        perfect_snapshot = build_market_snapshot(perfect_lot)
        defect_snapshot = build_market_snapshot(defect_lot)

        self.assertEqual(perfect_snapshot.current_unit_value, Decimal("110"))
        self.assertEqual(defect_snapshot.current_unit_value, Decimal("85"))

    def test_owned_lot_create_form_defaults_for_card_and_sealed(self):
        card_form = OwnedLotCreateForm(
            data={
                "kind": "CARD",
                "series": "",
                "extension": str(self.extension.id),
                "collectible_name": "Dracaufeu",
                "collectible_description": "",
                "card_number": "4/102",
                "rarity": "Rare Holo",
                "variant": "",
                "language": "FR",
                "card_condition": "NEW",
                "platform": "",
                "custom_description": "",
                "notes": "",
                "initial_operation_type": "BUY",
                "initial_quantity": "1",
                "initial_unit_price": "25.00",
                "initial_fees": "0",
                "initial_operation_date": "2026-03-01",
            }
        )
        self.assertTrue(card_form.is_valid(), card_form.errors)
        card_lot = card_form.save(self.user)
        self.assertEqual(card_lot.language, "FR")
        self.assertEqual(card_lot.card_condition, "NEW")
        self.assertFalse(card_lot.is_graded)

        sealed_form = OwnedLotCreateForm(
            data={
                "kind": "SEALED",
                "series": str(self.series.id),
                "extension": str(self.extension.id),
                "collectible_name": "Tripack Equilibre parfait",
                "collectible_description": "",
                "product_type": "TRIPACK",
                "language": "FR",
                "sealed_condition": "PERFECT",
                "platform": "",
                "custom_description": "",
                "notes": "",
                "initial_operation_type": "ADD",
                "initial_quantity": "1",
                "initial_fees": "0",
                "initial_operation_date": "2026-03-01",
            }
        )
        self.assertTrue(sealed_form.is_valid(), sealed_form.errors)
        sealed_lot = sealed_form.save(self.user)
        self.assertEqual(sealed_lot.language, "FR")
        self.assertEqual(sealed_lot.sealed_condition, "PERFECT")
        self.assertEqual(sealed_lot.collectible.sealed_details.product_type, "TRIPACK")

    def test_series_extension_form_behavior_is_dependent(self):
        filtered_form = OwnedLotCreateForm(data={"kind": "CARD", "series": str(self.series.id)})
        filtered_ids = list(filtered_form.fields["extension"].queryset.values_list("id", flat=True))
        self.assertEqual(filtered_ids, [self.extension.id])

        auto_series_form = OwnedLotCreateForm(
            data={
                "kind": "CARD",
                "series": "",
                "extension": str(self.other_extension.id),
                "collectible_name": "Noctali",
                "collectible_description": "",
                "card_number": "10/100",
                "rarity": "Rare",
                "variant": "",
                "language": "FR",
                "card_condition": "NM",
            }
        )
        self.assertEqual(auto_series_form["series"].value(), str(self.other_series.id))

    def test_collection_cards_view_filters_by_language_and_grade(self):
        raw_fr = OwnedLot.objects.create(user=self.user, collectible=self.card, language="FR", card_condition="NM")
        graded_en = OwnedLot.objects.create(
            user=self.user,
            collectible=self.card,
            language="EN",
            is_graded=True,
            grading_company="PSA",
            grading_grade="10",
        )
        self._buy(raw_fr, "1", "10", "2026-03-01")
        self._buy(graded_en, "1", "120", "2026-03-01")
        recompute_lot_metrics(raw_fr)
        recompute_lot_metrics(graded_en)

        response = self.client.get(reverse("pokeboard:collection"), {"tab": "cards", "language": "EN", "is_graded": "1"})
        self.assertEqual(response.status_code, 200)
        lots = response.context["lots"]
        self.assertEqual(len(lots), 1)
        self.assertEqual(lots[0].id, graded_en.id)
        self.assertEqual(lots[0].language, "EN")
        self.assertTrue(lots[0].is_graded)

    def test_collection_sealed_view_filters_by_product_type_and_condition(self):
        etb_lot = OwnedLot.objects.create(user=self.user, collectible=self.sealed, language="FR", sealed_condition="PERFECT")
        deck = Collectible.objects.create(kind="SEALED", extension=self.extension, name="Deck Equilibre parfait")
        SealedProductDetails.objects.create(collectible=deck, product_type="DECK")
        deck_lot = OwnedLot.objects.create(user=self.user, collectible=deck, language="FR", sealed_condition="DAMAGED")
        self._buy(etb_lot, "1", "70", "2026-03-01")
        self._buy(deck_lot, "1", "20", "2026-03-01")
        recompute_lot_metrics(etb_lot)
        recompute_lot_metrics(deck_lot)

        response = self.client.get(
            reverse("pokeboard:collection"),
            {"tab": "sealed", "product_type": "DECK", "sealed_condition": "DAMAGED"},
        )
        self.assertContains(response, "Deck Equilibre parfait")
        self.assertNotContains(response, "ETB Equilibre parfait")

    def test_contextual_actions_prefill_operation_and_valuation_forms(self):
        lot = OwnedLot.objects.create(user=self.user, collectible=self.card, language="FR", card_condition="NM")

        op_response = self.client.get(reverse("pokeboard:add_operation"), {"lot": lot.id})
        self.assertContains(op_response, "Lot cible")
        self.assertContains(op_response, f'value="{lot.id}"')

        valuation_response = self.client.get(reverse("pokeboard:add_valuation"), {"lot": lot.id})
        self.assertContains(valuation_response, "Variante cible")
        self.assertContains(valuation_response, "Pikachu ex")

    def test_stale_valuation_view_shows_only_stale_or_missing_by_default(self):
        stale_lot = OwnedLot.objects.create(user=self.user, collectible=self.card, language="FR", card_condition="NM")
        fresh_lot = OwnedLot.objects.create(user=self.user, collectible=self.card, language="EN", card_condition="NM")
        self._buy(stale_lot, "1", "9", "2026-03-01")
        self._buy(fresh_lot, "1", "12", "2026-03-01")
        recompute_lot_metrics(stale_lot)
        recompute_lot_metrics(fresh_lot)

        old_date = timezone.now().date() - timedelta(days=120)
        recent_date = timezone.now().date() - timedelta(days=10)
        CollectibleValuation.objects.create(
            collectible=self.card,
            kind="CARD",
            language="FR",
            card_condition="NM",
            unit_value=Decimal("15"),
            valued_at=old_date,
            source_type="MANUAL",
        )
        CollectibleValuation.objects.create(
            collectible=self.card,
            kind="CARD",
            language="EN",
            card_condition="NM",
            unit_value=Decimal("18"),
            valued_at=recent_date,
            source_type="MANUAL",
        )

        stale_response = self.client.get(reverse("pokeboard:stale_valuations"))
        self.assertEqual(stale_response.status_code, 200)
        stale_ids = [lot.id for lot in stale_response.context["lots"]]
        self.assertEqual(stale_ids, [stale_lot.id])

        all_response = self.client.get(reverse("pokeboard:stale_valuations"), {"scope": "all"})
        self.assertEqual(all_response.status_code, 200)
        all_ids = {lot.id for lot in all_response.context["lots"]}
        self.assertEqual(all_ids, {stale_lot.id, fresh_lot.id})

    def test_multi_user_isolation_is_preserved_in_collection_view(self):
        my_lot = OwnedLot.objects.create(user=self.user, collectible=self.card, language="FR", card_condition="NM")
        other_lot = OwnedLot.objects.create(user=self.other_user, collectible=self.card, language="EN", card_condition="NM")
        self._buy(my_lot, "1", "10", "2026-03-01", user=self.user)
        self._buy(other_lot, "1", "999", "2026-03-01", user=self.other_user)
        recompute_lot_metrics(my_lot)
        recompute_lot_metrics(other_lot)

        response = self.client.get(reverse("pokeboard:collection"), {"tab": "cards"})
        self.assertContains(response, "Pikachu ex")
        self.assertNotContains(response, "999")
