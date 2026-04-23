from __future__ import annotations

from decimal import Decimal

from django import forms
from django.forms import formset_factory
from django.utils import timezone

from .models import (
    CARD_CONDITION_CHOICES,
    COLLECTIBLE_KIND_CHOICES,
    GRADING_COMPANY_CHOICES,
    LANGUAGE_CHOICES,
    PRODUCT_TYPE_CHOICES,
    SEALED_CONDITION_CHOICES,
    CardDetails,
    Collectible,
    CollectibleValuation,
    CollectionOperation,
    OwnedLot,
    PokemonExtension,
    PokemonSeries,
    SealedProductDetails,
)
from .services import compute_operation_total, recompute_lot_metrics


class ExtensionSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-series-id"] = str(instance.series_id)
        return option


def _selected_value(data, key: str):
    if not data:
        return None
    value = data.get(key)
    return value or None


def _configure_series_extension_fields(form, prefix: str = ""):
    series_key = f"{prefix}series" if prefix else "series"
    extension_key = f"{prefix}extension" if prefix else "extension"
    if form.is_bound:
        form.data = form.data.copy()
    selected_series = _selected_value(form.data, series_key) if form.is_bound else None
    selected_extension = _selected_value(form.data, extension_key) if form.is_bound else None

    extension_qs = PokemonExtension.objects.select_related("series").order_by("series__era_order", "name")
    if selected_extension and not selected_series:
        extension = extension_qs.filter(pk=selected_extension).first()
        if extension:
            if form.is_bound:
                form.data[series_key] = str(extension.series_id)
            form.initial["series"] = extension.series_id
            selected_series = str(extension.series_id)

    if selected_series:
        extension_qs = extension_qs.filter(series_id=selected_series)

    form.fields["series"].queryset = PokemonSeries.objects.order_by("era_order", "name")
    form.fields["extension"].queryset = extension_qs


class OwnedLotCreateForm(forms.ModelForm):
    kind = forms.ChoiceField(
        choices=COLLECTIBLE_KIND_CHOICES,
        initial="CARD",
        label="Nature de l'item",
        widget=forms.Select(attrs={"class": "form-select", "data-pokeboard-kind": "true"}),
    )
    series = forms.ModelChoiceField(
        queryset=PokemonSeries.objects.order_by("era_order", "name"),
        required=False,
        label="Serie",
        widget=forms.Select(attrs={"class": "form-select", "data-pokeboard-series": "true"}),
    )
    extension = forms.ModelChoiceField(
        queryset=PokemonExtension.objects.select_related("series").order_by("series__era_order", "name"),
        required=False,
        label="Extension",
        widget=ExtensionSelect(attrs={"class": "form-select", "data-pokeboard-extension": "true"}),
    )
    collectible_name = forms.CharField(
        required=False,
        label="Nom de l'item",
        widget=forms.TextInput(attrs={"class": "form-control", "data-pokeboard-name": "true"}),
    )
    collectible_description = forms.CharField(
        required=False,
        label="Description catalogue",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    card_number = forms.CharField(
        required=False,
        label="Numero de carte",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    rarity = forms.CharField(
        required=False,
        label="Rarete",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    variant = forms.CharField(
        required=False,
        label="Variant",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    product_type = forms.ChoiceField(
        required=False,
        choices=[("", "---------")] + list(PRODUCT_TYPE_CHOICES),
        label="Type d'item scelle",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        initial="FR",
        label="Langue",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    card_condition = forms.ChoiceField(
        required=False,
        choices=CARD_CONDITION_CHOICES,
        initial="NEW",
        label="Etat de la carte",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_graded = forms.BooleanField(
        required=False,
        label="Carte gradee",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    grading_company = forms.ChoiceField(
        required=False,
        choices=[("", "---------")] + list(GRADING_COMPANY_CHOICES),
        label="Societe de gradation",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    grading_grade = forms.CharField(
        required=False,
        label="Grade",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 10, 9.5, Black Label"}),
    )
    sealed_condition = forms.ChoiceField(
        required=False,
        choices=SEALED_CONDITION_CHOICES,
        initial="PERFECT",
        label="Etat du scellage",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    initial_operation_type = forms.ChoiceField(
        required=False,
        choices=[("", "Aucune"), ("BUY", "Achat"), ("ADD", "Don / cadeau")],
        label="Type d'operation",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    initial_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        label="Quantite",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1"}),
    )
    initial_unit_price = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        decimal_places=2,
        label="Prix unitaire (EUR)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    initial_fees = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        decimal_places=2,
        label="Frais (EUR)",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
    )
    initial_operation_date = forms.DateField(
        required=False,
        label="Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    class Meta:
        model = OwnedLot
        fields = [
            "language",
            "card_condition",
            "is_graded",
            "grading_company",
            "grading_grade",
            "sealed_condition",
            "platform",
            "custom_description",
            "notes",
        ]
        widgets = {
            "platform": forms.TextInput(attrs={"class": "form-control"}),
            "custom_description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "custom_description": "Description personnalisee",
            "notes": "Notes",
            "platform": "Plateforme par defaut",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_series_extension_fields(self)
        self.fields["initial_operation_date"].initial = timezone.now().date()
        self.fields["initial_fees"].initial = Decimal("0")

    def build_default_collectible_name(self, cleaned_data):
        extension = cleaned_data.get("extension")
        extension_code = extension.code if extension else "EXT"
        kind = cleaned_data.get("kind")
        if kind == "SEALED":
            product_type = cleaned_data.get("product_type") or "ITEM"
            return f"{product_type} {extension_code} <nom personnalise>"

        base_name = (cleaned_data.get("collectible_name") or "").strip() or "Carte"
        card_number = (cleaned_data.get("card_number") or "").strip() or "000/000"
        return f"Carte {extension_code} {base_name} {card_number}"

    def clean(self):
        cleaned = super().clean()
        collectible_name = (cleaned.get("collectible_name") or "").strip()
        extension = cleaned.get("extension")
        initial_type = cleaned.get("initial_operation_type")
        initial_quantity = cleaned.get("initial_quantity")
        initial_unit_price = cleaned.get("initial_unit_price")
        kind = cleaned.get("kind")
        is_graded = cleaned.get("is_graded")
        cleaned["collectible_name"] = collectible_name

        if not extension:
            self.add_error("extension", "Une extension est obligatoire pour creer un item catalogue.")
        elif not collectible_name:
            cleaned["collectible_name"] = self.build_default_collectible_name(cleaned)

        if kind == "CARD":
            cleaned["sealed_condition"] = None
            if cleaned.get("product_type"):
                self.add_error("product_type", "Le type scelle ne s'applique pas a une carte.")
            if is_graded:
                cleaned["card_condition"] = None
                if not cleaned.get("grading_company"):
                    self.add_error("grading_company", "La societe de gradation est obligatoire.")
                if not cleaned.get("grading_grade"):
                    self.add_error("grading_grade", "Le grade est obligatoire pour une carte gradee.")
            else:
                cleaned["grading_company"] = None
                cleaned["grading_grade"] = None
                if not cleaned.get("card_condition"):
                    self.add_error("card_condition", "L'etat de la carte est obligatoire.")
        elif kind == "SEALED":
            cleaned["card_condition"] = None
            cleaned["is_graded"] = False
            cleaned["grading_company"] = None
            cleaned["grading_grade"] = None
            if any(cleaned.get(field) for field in ("card_number", "rarity", "variant")):
                self.add_error("card_number", "Les champs de carte ne s'appliquent pas a un item scelle.")
            if not cleaned.get("product_type"):
                self.add_error("product_type", "Le type d'item scelle est obligatoire.")
            if not cleaned.get("sealed_condition"):
                self.add_error("sealed_condition", "L'etat du scellage est obligatoire.")

        if initial_type and not initial_quantity:
            self.add_error("initial_quantity", "La quantite est obligatoire si vous creez une operation.")
        if initial_type == "BUY" and initial_unit_price is None:
            self.add_error("initial_unit_price", "Le prix unitaire est obligatoire pour un achat.")
        return cleaned

    def save(self, user, commit=True):
        collectible = Collectible.objects.create(
            kind=self.cleaned_data["kind"],
            extension=self.cleaned_data["extension"],
            name=self.cleaned_data["collectible_name"] or self.build_default_collectible_name(self.cleaned_data),
            description=self.cleaned_data["collectible_description"],
        )
        if collectible.kind == "CARD":
            CardDetails.objects.create(
                collectible=collectible,
                card_number=self.cleaned_data["card_number"],
                rarity=self.cleaned_data["rarity"],
                variant=self.cleaned_data["variant"],
            )
        else:
            SealedProductDetails.objects.create(
                collectible=collectible,
                product_type=self.cleaned_data["product_type"] or "OTHER",
            )

        lot = super().save(commit=False)
        lot.user = user
        lot.collectible = collectible
        lot.language = self.cleaned_data["language"] or "FR"
        if collectible.kind == "CARD":
            lot.card_condition = None if self.cleaned_data.get("is_graded") else self.cleaned_data.get("card_condition") or "NEW"
            lot.is_graded = bool(self.cleaned_data.get("is_graded"))
            lot.grading_company = self.cleaned_data.get("grading_company") or None
            lot.grading_grade = self.cleaned_data.get("grading_grade") or None
            lot.sealed_condition = None
        else:
            lot.card_condition = None
            lot.is_graded = False
            lot.grading_company = None
            lot.grading_grade = None
            lot.sealed_condition = self.cleaned_data.get("sealed_condition") or "PERFECT"
        if commit:
            lot.save()

        initial_type = self.cleaned_data.get("initial_operation_type")
        if initial_type:
            quantity = self.cleaned_data["initial_quantity"]
            unit_price = self.cleaned_data.get("initial_unit_price")
            fees = self.cleaned_data.get("initial_fees") or Decimal("0")
            total = compute_operation_total(initial_type, quantity, unit_price, fees)
            CollectionOperation.objects.create(
                user=user,
                lot=lot,
                operation_type=initial_type,
                operation_date=self.cleaned_data["initial_operation_date"] or timezone.now().date(),
                quantity=quantity,
                unit_price=unit_price,
                total_price=total,
                fees=fees,
                platform=self.cleaned_data.get("platform") or "",
                comment="Operation initiale",
            )
            recompute_lot_metrics(lot)

        return lot


class CollectionOperationForm(forms.ModelForm):
    next_url = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = CollectionOperation
        fields = [
            "lot",
            "operation_type",
            "operation_date",
            "quantity",
            "unit_price",
            "fees",
            "platform",
            "comment",
        ]
        widgets = {
            "lot": forms.Select(attrs={"class": "form-select"}),
            "operation_type": forms.Select(attrs={"class": "form-select"}),
            "operation_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "1"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "fees": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "platform": forms.TextInput(attrs={"class": "form-control"}),
            "comment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, user, *args, **kwargs):
        lot = kwargs.pop("lot", None)
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["lot"].queryset = OwnedLot.objects.filter(user=user).select_related(
            "collectible", "collectible__extension", "collectible__extension__series"
        )
        self.fields["operation_date"].initial = timezone.now().date()
        self.fields["fees"].initial = Decimal("0")
        if lot is not None:
            self.fields["lot"].initial = lot
            self.fields["lot"].widget = forms.HiddenInput()
            self.lot = lot
        else:
            self.lot = None

    def clean(self):
        cleaned = super().clean()
        lot = cleaned.get("lot") or getattr(self, "lot", None)
        if lot and not cleaned.get("lot"):
            cleaned["lot"] = lot
        op_type = cleaned.get("operation_type")
        quantity = cleaned.get("quantity")
        unit_price = cleaned.get("unit_price")
        fees = cleaned.get("fees") or Decimal("0")

        if lot and lot.user_id != self.user.id:
            self.add_error("lot", "Ce lot ne vous appartient pas.")
            return cleaned

        if quantity is None:
            return cleaned

        if quantity != int(quantity):
            self.add_error("quantity", "La quantite doit etre un nombre entier.")

        if op_type in {"BUY", "SELL", "ADD"} and quantity <= 0:
            self.add_error("quantity", "La quantite doit etre positive pour cette operation.")

        if op_type == "SELL" and lot and quantity > lot.remaining_quantity:
            self.add_error("quantity", "La vente depasse la quantite actuellement disponible sur le lot.")

        if op_type == "ADJUST" and lot:
            new_qty = lot.remaining_quantity + quantity
            if new_qty < 0:
                self.add_error("quantity", "La correction ferait passer le stock sous zero.")

        if op_type in {"BUY", "SELL"} and unit_price is None:
            self.add_error("unit_price", "Le prix unitaire est obligatoire pour un achat ou une vente.")

        cleaned["total_price"] = compute_operation_total(op_type, quantity, unit_price, fees)
        return cleaned

    def save(self, commit=True):
        operation = super().save(commit=False)
        operation.user = self.user
        operation.total_price = self.cleaned_data["total_price"]
        operation.lot = self.cleaned_data["lot"]
        if commit:
            operation.save()
            recompute_lot_metrics(operation.lot)
        return operation


class CollectibleValuationForm(forms.ModelForm):
    next_url = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = CollectibleValuation
        fields = [
            "collectible",
            "kind",
            "language",
            "card_condition",
            "is_graded",
            "grading_company",
            "grading_grade",
            "sealed_condition",
            "unit_value",
            "valued_at",
            "source_type",
            "notes",
        ]
        widgets = {
            "collectible": forms.Select(attrs={"class": "form-select"}),
            "kind": forms.Select(attrs={"class": "form-select", "data-pokeboard-kind": "true"}),
            "language": forms.Select(attrs={"class": "form-select"}),
            "card_condition": forms.Select(attrs={"class": "form-select"}),
            "is_graded": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "grading_company": forms.Select(attrs={"class": "form-select"}),
            "grading_grade": forms.TextInput(attrs={"class": "form-control"}),
            "sealed_condition": forms.Select(attrs={"class": "form-select"}),
            "unit_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "valued_at": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        lot = kwargs.pop("lot", None)
        super().__init__(*args, **kwargs)
        self.fields["collectible"].queryset = Collectible.objects.select_related(
            "extension", "extension__series"
        ).order_by("extension__series__era_order", "extension__name", "name")
        self.fields["valued_at"].initial = timezone.now().date()
        self.fields["kind"].choices = COLLECTIBLE_KIND_CHOICES
        self.fields["kind"].initial = "CARD"
        self.fields["language"].choices = LANGUAGE_CHOICES
        self.fields["language"].initial = "FR"
        self.fields["card_condition"].choices = CARD_CONDITION_CHOICES
        self.fields["card_condition"].initial = "NEW"
        self.fields["sealed_condition"].choices = SEALED_CONDITION_CHOICES
        self.fields["sealed_condition"].initial = "PERFECT"
        self.fields["grading_company"].choices = [("", "---------")] + list(GRADING_COMPANY_CHOICES)
        self.lot = lot

        if lot is not None:
            self.fields["collectible"].initial = lot.collectible
            self.fields["kind"].initial = lot.collectible.kind
            self.fields["language"].initial = lot.language
            self.fields["is_graded"].initial = lot.is_graded
            self.fields["card_condition"].initial = lot.card_condition
            self.fields["grading_company"].initial = lot.grading_company
            self.fields["grading_grade"].initial = lot.grading_grade
            self.fields["sealed_condition"].initial = lot.sealed_condition
            for name in [
                "collectible",
                "kind",
                "language",
                "is_graded",
                "card_condition",
                "grading_company",
                "grading_grade",
                "sealed_condition",
            ]:
                self.fields[name].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if self.lot is not None:
            cleaned["collectible"] = self.lot.collectible
            cleaned["kind"] = self.lot.collectible.kind
            cleaned["language"] = self.lot.language
            cleaned["is_graded"] = self.lot.is_graded
            cleaned["card_condition"] = self.lot.card_condition
            cleaned["grading_company"] = self.lot.grading_company
            cleaned["grading_grade"] = self.lot.grading_grade
            cleaned["sealed_condition"] = self.lot.sealed_condition
        return cleaned


class BaseVariantFilterForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=PokemonSeries.objects.order_by("era_order", "name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select", "data-pokeboard-series": "true"}),
    )
    extension = forms.ModelChoiceField(
        queryset=PokemonExtension.objects.select_related("series").order_by("series__era_order", "name"),
        required=False,
        widget=ExtensionSelect(attrs={"class": "form-select", "data-pokeboard-extension": "true"}),
    )
    language = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes")] + list(LANGUAGE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_graded = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes"), ("1", "Gradees"), ("0", "Non gradees")],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    grading_company = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes")] + list(GRADING_COMPANY_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    card_condition = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + list(CARD_CONDITION_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sealed_condition = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + list(SEALED_CONDITION_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    product_type = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + list(PRODUCT_TYPE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_series_extension_fields(self)


class CollectionFilterForm(BaseVariantFilterForm):
    pass


class ReportFilterForm(BaseVariantFilterForm):
    kind = forms.ChoiceField(
        required=False,
        choices=[("", "Tous")] + list(COLLECTIBLE_KIND_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    platform = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))


class BatchValuationLineForm(forms.Form):
    lot_id = forms.IntegerField(widget=forms.HiddenInput())
    next_url = forms.CharField(required=False, widget=forms.HiddenInput())
    unit_value = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "Nouvelle valeur"}),
    )
    valued_at = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )


BatchValuationFormSet = formset_factory(BatchValuationLineForm, extra=0)
