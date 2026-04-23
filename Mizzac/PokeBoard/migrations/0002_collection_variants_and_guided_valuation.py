from django.db import migrations, models


LEGACY_CARD_CONDITION_MAP = {
    "MINT": "NEW",
    "NM": "NM",
    "EX": "EX",
    "GD": "GD",
    "LP": "LP",
    "POOR": "DMG",
}

LEGACY_SEALED_CONDITION_MAP = {
    "MINT": "PERFECT",
    "NM": "PERFECT",
    "EX": "DEFECT",
    "GD": "DEFECT",
    "LP": "DEFECT",
    "POOR": "DAMAGED",
}


def backfill_collection_variants(apps, schema_editor):
    CardDetails = apps.get_model("PokeBoard", "CardDetails")
    OwnedLot = apps.get_model("PokeBoard", "OwnedLot")
    CollectibleValuation = apps.get_model("PokeBoard", "CollectibleValuation")

    card_language_map = {
        detail.collectible_id: (detail.language or "FR")
        for detail in CardDetails.objects.all().only("collectible_id", "language")
    }

    for lot in OwnedLot.objects.select_related("collectible").all():
        kind = lot.collectible.kind
        lot.language = card_language_map.get(lot.collectible_id, "FR")
        lot.is_graded = False
        lot.grading_company = None
        lot.grading_grade = None
        if kind == "CARD":
            lot.card_condition = LEGACY_CARD_CONDITION_MAP.get(getattr(lot, "condition", None), "NEW")
            lot.sealed_condition = None
        else:
            lot.card_condition = None
            lot.sealed_condition = LEGACY_SEALED_CONDITION_MAP.get(getattr(lot, "condition", None), "PERFECT")
        lot.save(
            update_fields=[
                "language",
                "card_condition",
                "is_graded",
                "grading_company",
                "grading_grade",
                "sealed_condition",
                "updated_at",
            ]
        )

    for valuation in CollectibleValuation.objects.select_related("collectible").all():
        kind = valuation.collectible.kind
        valuation.kind = kind
        valuation.language = card_language_map.get(valuation.collectible_id, "FR")
        valuation.is_graded = False
        valuation.grading_company = None
        valuation.grading_grade = None
        if kind == "CARD":
            valuation.card_condition = LEGACY_CARD_CONDITION_MAP.get(getattr(valuation, "condition", None), "NEW")
            valuation.sealed_condition = None
        else:
            valuation.card_condition = None
            valuation.sealed_condition = LEGACY_SEALED_CONDITION_MAP.get(getattr(valuation, "condition", None), "PERFECT")
        valuation.save(
            update_fields=[
                "kind",
                "language",
                "card_condition",
                "is_graded",
                "grading_company",
                "grading_grade",
                "sealed_condition",
                "updated_at",
            ]
        )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("PokeBoard", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="ownedlot",
            options={
                "ordering": ["collectible__extension__series__era_order", "collectible__extension__name", "collectible__name"],
                "verbose_name": "Element de collection",
                "verbose_name_plural": "Elements de collection",
            },
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="language",
            field=models.CharField(
                choices=[
                    ("FR", "Francais"),
                    ("EN", "Anglais"),
                    ("ES", "Espagnol"),
                    ("IT", "Italien"),
                    ("DE", "Allemand"),
                    ("PT", "Portugais"),
                    ("NL", "Neerlandais"),
                    ("JA", "Japonais"),
                    ("KO", "Coreen"),
                    ("ZH_HANS", "Chinois simplifie"),
                    ("ZH_HANT", "Chinois traditionnel"),
                    ("OTHER", "Autre"),
                ],
                default="FR",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="card_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NEW", "Neuf"),
                    ("NM", "Tres bon etat"),
                    ("EX", "Excellent"),
                    ("GD", "Bon"),
                    ("LP", "Legerement joue"),
                    ("PL", "Joue"),
                    ("DMG", "Abime"),
                ],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="is_graded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="grading_company",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PSA", "PSA"),
                    ("PCA", "PCA"),
                    ("BGS", "BGS"),
                    ("CGC", "CGC"),
                    ("ACE", "ACE"),
                    ("SGC", "SGC"),
                    ("OTHER", "Autre"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="grading_grade",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="ownedlot",
            name="sealed_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PERFECT", "Scellage parfait"),
                    ("DEFECT", "Scellage abime"),
                    ("LOOSE", "Non scelle (en loose)"),
                    ("DAMAGED", "Abime"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="kind",
            field=models.CharField(choices=[("CARD", "Carte"), ("SEALED", "Scelle")], default="CARD", max_length=10),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="language",
            field=models.CharField(
                choices=[
                    ("FR", "Francais"),
                    ("EN", "Anglais"),
                    ("ES", "Espagnol"),
                    ("IT", "Italien"),
                    ("DE", "Allemand"),
                    ("PT", "Portugais"),
                    ("NL", "Neerlandais"),
                    ("JA", "Japonais"),
                    ("KO", "Coreen"),
                    ("ZH_HANS", "Chinois simplifie"),
                    ("ZH_HANT", "Chinois traditionnel"),
                    ("OTHER", "Autre"),
                ],
                default="FR",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="card_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("NEW", "Neuf"),
                    ("NM", "Tres bon etat"),
                    ("EX", "Excellent"),
                    ("GD", "Bon"),
                    ("LP", "Legerement joue"),
                    ("PL", "Joue"),
                    ("DMG", "Abime"),
                ],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="is_graded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="grading_company",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PSA", "PSA"),
                    ("PCA", "PCA"),
                    ("BGS", "BGS"),
                    ("CGC", "CGC"),
                    ("ACE", "ACE"),
                    ("SGC", "SGC"),
                    ("OTHER", "Autre"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="grading_grade",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="collectiblevaluation",
            name="sealed_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PERFECT", "Scellage parfait"),
                    ("DEFECT", "Scellage abime"),
                    ("LOOSE", "Non scelle (en loose)"),
                    ("DAMAGED", "Abime"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="sealedproductdetails",
            name="product_type",
            field=models.CharField(
                choices=[
                    ("BOOSTER", "Booster"),
                    ("PACK", "Paquet"),
                    ("DECK", "Deck"),
                    ("POKEBOX", "Pokebox"),
                    ("POKEBALL", "Pokeball"),
                    ("ETB", "ETB"),
                    ("UTB", "UTB"),
                    ("UPC", "UPC"),
                    ("TRIPACK", "Tripack"),
                    ("DUOPACK", "Duopack"),
                    ("DISPLAY", "Display"),
                    ("BUNDLE", "Bundle"),
                    ("COFFRET", "Coffret"),
                    ("TIN", "Tin"),
                    ("MINI_TIN", "Mini tin"),
                    ("OTHER", "Autre"),
                ],
                default="OTHER",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_collection_variants, noop_reverse),
        migrations.RemoveConstraint(
            model_name="collectiblevaluation",
            name="pokeboard_valuation_unique_entry",
        ),
        migrations.RemoveIndex(
            model_name="ownedlot",
            name="PokeBoard_o_user_id_013f29_idx",
        ),
        migrations.RemoveIndex(
            model_name="collectiblevaluation",
            name="PokeBoard_c_collect_8b333b_idx",
        ),
        migrations.RemoveField(
            model_name="carddetails",
            name="language",
        ),
        migrations.RemoveField(
            model_name="ownedlot",
            name="condition",
        ),
        migrations.RemoveField(
            model_name="collectiblevaluation",
            name="condition",
        ),
        migrations.AddConstraint(
            model_name="collectiblevaluation",
            constraint=models.UniqueConstraint(
                fields=(
                    "collectible",
                    "kind",
                    "language",
                    "card_condition",
                    "is_graded",
                    "grading_company",
                    "grading_grade",
                    "sealed_condition",
                    "valued_at",
                    "source_type",
                ),
                name="pokeboard_valuation_unique_entry",
            ),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "language"], name="pokeboard_lot_user_lang_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "card_condition"], name="pokeboard_lot_user_card_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "is_graded"], name="pokeboard_lot_user_grad_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "sealed_condition"], name="pokeboard_lot_user_seal_idx"),
        ),
        migrations.AddIndex(
            model_name="collectiblevaluation",
            index=models.Index(fields=["collectible", "kind", "language", "valued_at"], name="pokeboard_val_variant_idx"),
        ),
        migrations.AddIndex(
            model_name="collectiblevaluation",
            index=models.Index(fields=["collectible", "is_graded", "valued_at"], name="pokeboard_val_graded_idx"),
        ),
    ]
