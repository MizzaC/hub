from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import CheckConstraint, Q
from django.template.defaultfilters import slugify
from django.utils import timezone


COLLECTIBLE_KIND_CHOICES = [
    ("CARD", "Carte"),
    ("SEALED", "Scelle"),
]

LANGUAGE_CHOICES = [
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
]

CARD_CONDITION_CHOICES = [
    ("NEW", "Neuf"),
    ("NM", "Tres bon etat"),
    ("EX", "Excellent"),
    ("GD", "Bon"),
    ("LP", "Legerement joue"),
    ("PL", "Joue"),
    ("DMG", "Abime"),
]

SEALED_CONDITION_CHOICES = [
    ("PERFECT", "Scellage parfait"),
    ("DEFECT", "Scellage abime"),
    ("LOOSE", "Non scelle (en loose)"),
    ("DAMAGED", "Abime"),
]

GRADING_COMPANY_CHOICES = [
    ("PSA", "PSA"),
    ("PCA", "PCA"),
    ("BGS", "BGS"),
    ("CGC", "CGC"),
    ("ACE", "ACE"),
    ("SGC", "SGC"),
    ("OTHER", "Autre"),
]

PRODUCT_TYPE_CHOICES = [
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
]

OPERATION_TYPE_CHOICES = [
    ("BUY", "Achat"),
    ("SELL", "Vente"),
    ("ADD", "Ajout manuel"),
    ("ADJUST", "Correction"),
]

VALUATION_SOURCE_CHOICES = [
    ("MANUAL", "Manuelle"),
    ("IMPORT", "Import"),
    ("API", "API"),
]


class PokemonSeries(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    era_order = models.PositiveIntegerField(default=0)
    source_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["era_order", "name"]
        verbose_name = "Serie Pokemon"
        verbose_name_plural = "Series Pokemon"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class PokemonExtension(models.Model):
    series = models.ForeignKey(PokemonSeries, on_delete=models.CASCADE, related_name="extensions")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=20, unique=True)
    release_date = models.DateField(null=True, blank=True)
    card_count = models.PositiveIntegerField(null=True, blank=True)
    source_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["series__era_order", "release_date", "name"]
        verbose_name = "Extension Pokemon"
        verbose_name_plural = "Extensions Pokemon"
        constraints = [
            models.UniqueConstraint(fields=["series", "name"], name="pokeboard_extension_series_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["series", "name"], name="PokeBoard_p_series__877793_idx"),
            models.Index(fields=["code"], name="PokeBoard_p_code_98db6c_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Collectible(models.Model):
    kind = models.CharField(max_length=10, choices=COLLECTIBLE_KIND_CHOICES)
    extension = models.ForeignKey(PokemonExtension, on_delete=models.CASCADE, related_name="collectibles")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["extension__series__era_order", "extension__name", "name"]
        verbose_name = "Item catalogue"
        verbose_name_plural = "Items catalogue"
        indexes = [
            models.Index(fields=["extension", "kind"], name="PokeBoard_c_extensi_ae27ab_idx"),
            models.Index(fields=["name"], name="PokeBoard_c_name_339940_idx"),
        ]

    @property
    def card_details_safe(self):
        try:
            return self.card_details
        except CardDetails.DoesNotExist:
            return None

    @property
    def sealed_details_safe(self):
        try:
            return self.sealed_details
        except SealedProductDetails.DoesNotExist:
            return None

    @property
    def display_name(self) -> str:
        if self.kind == "CARD" and self.card_details_safe and self.card_details_safe.card_number:
            return f"{self.name} #{self.card_details_safe.card_number}"
        return self.name

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_kind_display()})"


class CardDetails(models.Model):
    collectible = models.OneToOneField(Collectible, on_delete=models.CASCADE, related_name="card_details")
    card_number = models.CharField(max_length=40, blank=True)
    rarity = models.CharField(max_length=80, blank=True)
    variant = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name = "Detail carte"
        verbose_name_plural = "Details cartes"

    def clean(self):
        if self.collectible.kind != "CARD":
            raise ValidationError("Les details de carte ne peuvent etre lies qu'a un item de type carte.")

    def __str__(self) -> str:
        return f"{self.collectible.name} - {self.card_number or 'sans numero'}"


class SealedProductDetails(models.Model):
    collectible = models.OneToOneField(Collectible, on_delete=models.CASCADE, related_name="sealed_details")
    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default="OTHER")

    class Meta:
        verbose_name = "Detail produit scelle"
        verbose_name_plural = "Details produits scelles"

    def clean(self):
        if self.collectible.kind != "SEALED":
            raise ValidationError("Les details de produit scelle ne peuvent etre lies qu'a un item scelle.")

    def __str__(self) -> str:
        return f"{self.collectible.name} - {self.get_product_type_display()}"


class OwnedLot(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pokemon_lots")
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE, related_name="lots")
    language = models.CharField(max_length=15, choices=LANGUAGE_CHOICES, default="FR")
    card_condition = models.CharField(max_length=10, choices=CARD_CONDITION_CHOICES, null=True, blank=True)
    is_graded = models.BooleanField(default=False)
    grading_company = models.CharField(max_length=20, choices=GRADING_COMPANY_CHOICES, null=True, blank=True)
    grading_grade = models.CharField(max_length=20, blank=True, null=True)
    sealed_condition = models.CharField(max_length=20, choices=SEALED_CONDITION_CHOICES, null=True, blank=True)
    platform = models.CharField(max_length=120, blank=True)
    custom_description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    remaining_quantity = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0"))
    acquisition_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    average_unit_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    realized_pnl_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["collectible__extension__series__era_order", "collectible__extension__name", "collectible__name"]
        verbose_name = "Element de collection"
        verbose_name_plural = "Elements de collection"
        indexes = [
            models.Index(fields=["user", "collectible"], name="PokeBoard_o_user_id_3b8e89_idx"),
            models.Index(fields=["user", "language"], name="pokeboard_lot_user_lang_idx"),
            models.Index(fields=["user", "card_condition"], name="pokeboard_lot_user_card_idx"),
            models.Index(fields=["user", "is_graded"], name="pokeboard_lot_user_grad_idx"),
            models.Index(fields=["user", "sealed_condition"], name="pokeboard_lot_user_seal_idx"),
            models.Index(fields=["user", "platform"], name="PokeBoard_o_user_id_b6e56a_idx"),
        ]

    @property
    def is_card(self) -> bool:
        return self.collectible.kind == "CARD"

    @property
    def is_sealed(self) -> bool:
        return self.collectible.kind == "SEALED"

    @property
    def description_text(self) -> str:
        return self.custom_description or self.collectible.description

    @property
    def display_name(self) -> str:
        return self.collectible.display_name

    @property
    def state_label(self) -> str:
        if self.is_card:
            if self.is_graded and self.grading_company and self.grading_grade:
                return f"{self.grading_company} {self.grading_grade}"
            return self.get_card_condition_display() if self.card_condition else "-"
        return self.get_sealed_condition_display() if self.sealed_condition else "-"

    @property
    def language_label(self) -> str:
        return self.get_language_display()

    @property
    def variant_label(self) -> str:
        if self.is_card and self.is_graded:
            return f"{self.language_label} - Gradée {self.state_label}"
        return f"{self.language_label} - {self.state_label}"

    @property
    def product_type_label(self) -> str:
        if self.is_sealed and self.collectible.sealed_details_safe:
            return self.collectible.sealed_details_safe.get_product_type_display()
        return "-"

    def valuation_lookup(self) -> dict:
        data = {
            "collectible": self.collectible,
            "kind": self.collectible.kind,
            "language": self.language,
            "is_graded": self.is_graded,
        }
        if self.is_card:
            data["card_condition"] = None if self.is_graded else self.card_condition
            data["sealed_condition"] = None
            data["grading_company"] = self.grading_company if self.is_graded else None
            data["grading_grade"] = self.grading_grade if self.is_graded else None
        else:
            data["card_condition"] = None
            data["sealed_condition"] = self.sealed_condition
            data["grading_company"] = None
            data["grading_grade"] = None
        return data

    def clean(self):
        if self.collectible_id and self.collectible.kind == "CARD":
            if not self.card_condition and not self.is_graded:
                raise ValidationError({"card_condition": "L'etat de la carte est obligatoire pour une carte non gradee."})
            if self.is_graded:
                if not self.grading_company:
                    raise ValidationError({"grading_company": "La societe de gradation est obligatoire."})
                if not self.grading_grade:
                    raise ValidationError({"grading_grade": "Le grade est obligatoire pour une carte gradee."})
            if self.sealed_condition:
                raise ValidationError({"sealed_condition": "L'etat de scellage ne s'applique pas a une carte."})
        elif self.collectible_id and self.collectible.kind == "SEALED":
            if not self.sealed_condition:
                raise ValidationError({"sealed_condition": "L'etat de scellage est obligatoire pour un item scelle."})
            if self.is_graded:
                raise ValidationError({"is_graded": "Un item scelle ne peut pas etre marque comme gradé."})
            if self.card_condition:
                raise ValidationError({"card_condition": "L'etat de carte ne s'applique pas a un item scelle."})
            if self.grading_company or self.grading_grade:
                raise ValidationError("Les champs de gradation ne s'appliquent pas aux items scelles.")

    def save(self, *args, **kwargs):
        if self.collectible_id:
            if self.collectible.kind == "CARD":
                self.sealed_condition = None
                if not self.is_graded and not self.card_condition:
                    self.card_condition = "NEW"
                if not self.is_graded:
                    self.grading_company = None
                    self.grading_grade = None
            else:
                self.card_condition = None
                self.is_graded = False
                self.grading_company = None
                self.grading_grade = None
                if not self.sealed_condition:
                    self.sealed_condition = "PERFECT"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.username} - {self.display_name} ({self.variant_label})"


class CollectionOperation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pokemon_operations")
    lot = models.ForeignKey(OwnedLot, on_delete=models.CASCADE, related_name="operations")
    operation_type = models.CharField(max_length=10, choices=OPERATION_TYPE_CHOICES)
    operation_date = models.DateField(default=timezone.now)
    quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    total_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    fees = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    platform = models.CharField(max_length=120, blank=True)
    comment = models.TextField(blank=True)
    realized_pnl = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-operation_date", "-id"]
        verbose_name = "Operation de collection"
        verbose_name_plural = "Operations de collection"
        indexes = [
            models.Index(fields=["user", "operation_date"], name="PokeBoard_c_user_id_767054_idx"),
            models.Index(fields=["lot", "operation_date"], name="PokeBoard_c_lot_id_b2fb57_idx"),
            models.Index(fields=["operation_type"], name="PokeBoard_c_operati_340525_idx"),
        ]
        constraints = [
            CheckConstraint(
                check=(Q(operation_type="ADJUST") | Q(quantity__gt=0)),
                name="pokeboard_operation_non_adjust_positive_quantity",
            ),
        ]

    @property
    def signed_quantity(self) -> Decimal:
        if self.operation_type == "SELL":
            return -abs(self.quantity)
        if self.operation_type == "ADJUST":
            return self.quantity
        return abs(self.quantity)

    @property
    def display_quantity(self) -> Decimal:
        return abs(self.quantity)

    @property
    def item_label(self) -> str:
        return self.lot.collectible.display_name

    def clean(self):
        if self.lot_id and self.user_id and self.lot.user_id != self.user_id:
            raise ValidationError("Le lot choisi n'appartient pas a cet utilisateur.")
        if self.operation_type in {"BUY", "SELL"} and self.unit_price is None:
            raise ValidationError({"unit_price": "Le prix unitaire est obligatoire pour un achat ou une vente."})
        if self.operation_type == "ADJUST" and self.quantity == 0:
            raise ValidationError({"quantity": "Une correction doit avoir un impact positif ou negatif."})

    def __str__(self) -> str:
        return f"{self.get_operation_type_display()} - {self.item_label} - {self.operation_date}"


class CollectibleValuation(models.Model):
    collectible = models.ForeignKey(Collectible, on_delete=models.CASCADE, related_name="valuations")
    kind = models.CharField(max_length=10, choices=COLLECTIBLE_KIND_CHOICES)
    language = models.CharField(max_length=15, choices=LANGUAGE_CHOICES, default="FR")
    card_condition = models.CharField(max_length=10, choices=CARD_CONDITION_CHOICES, null=True, blank=True)
    is_graded = models.BooleanField(default=False)
    grading_company = models.CharField(max_length=20, choices=GRADING_COMPANY_CHOICES, null=True, blank=True)
    grading_grade = models.CharField(max_length=20, blank=True, null=True)
    sealed_condition = models.CharField(max_length=20, choices=SEALED_CONDITION_CHOICES, null=True, blank=True)
    unit_value = models.DecimalField(max_digits=14, decimal_places=2)
    valued_at = models.DateField(default=timezone.now)
    source_type = models.CharField(max_length=10, choices=VALUATION_SOURCE_CHOICES, default="MANUAL")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-valued_at", "-id"]
        verbose_name = "Valorisation"
        verbose_name_plural = "Valorisations"
        constraints = [
            models.UniqueConstraint(
                fields=[
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
                ],
                name="pokeboard_valuation_unique_entry",
            )
        ]
        indexes = [
            models.Index(
                fields=["collectible", "kind", "language", "valued_at"],
                name="pokeboard_val_variant_idx",
            ),
            models.Index(fields=["collectible", "is_graded", "valued_at"], name="pokeboard_val_graded_idx"),
        ]

    @property
    def state_label(self) -> str:
        if self.kind == "CARD":
            if self.is_graded and self.grading_company and self.grading_grade:
                return f"{self.grading_company} {self.grading_grade}"
            return self.get_card_condition_display() if self.card_condition else "-"
        return self.get_sealed_condition_display() if self.sealed_condition else "-"

    def clean(self):
        if self.collectible_id and self.kind != self.collectible.kind:
            raise ValidationError({"kind": "Le type de valorisation doit correspondre a l'item catalogue."})
        if self.kind == "CARD":
            if self.is_graded:
                if not self.grading_company:
                    raise ValidationError({"grading_company": "La societe de gradation est obligatoire."})
                if not self.grading_grade:
                    raise ValidationError({"grading_grade": "Le grade est obligatoire."})
                self.card_condition = None
            elif not self.card_condition:
                raise ValidationError({"card_condition": "L'etat de carte est obligatoire pour une carte non gradee."})
            if self.sealed_condition:
                raise ValidationError({"sealed_condition": "L'etat de scellage ne s'applique pas a une carte."})
        elif self.kind == "SEALED":
            if self.is_graded:
                raise ValidationError({"is_graded": "Un item scelle ne peut pas etre gradé."})
            if not self.sealed_condition:
                raise ValidationError({"sealed_condition": "L'etat de scellage est obligatoire pour un item scelle."})
            self.card_condition = None
            self.grading_company = None
            self.grading_grade = None

    def save(self, *args, **kwargs):
        if self.collectible_id:
            self.kind = self.collectible.kind
        if self.kind == "CARD":
            self.sealed_condition = None
            if self.is_graded:
                self.card_condition = None
            else:
                self.grading_company = None
                self.grading_grade = None
                if not self.card_condition:
                    self.card_condition = "NEW"
        elif self.kind == "SEALED":
            self.card_condition = None
            self.is_graded = False
            self.grading_company = None
            self.grading_grade = None
            if not self.sealed_condition:
                self.sealed_condition = "PERFECT"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.collectible.display_name} - {self.get_language_display()} - {self.state_label} - {self.unit_value}"
