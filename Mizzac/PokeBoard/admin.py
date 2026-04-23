from django.contrib import admin

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


class PokemonExtensionInline(admin.TabularInline):
    model = PokemonExtension
    extra = 0


@admin.register(PokemonSeries)
class PokemonSeriesAdmin(admin.ModelAdmin):
    list_display = ("name", "era_order")
    search_fields = ("name",)
    inlines = [PokemonExtensionInline]


class CardDetailsInline(admin.StackedInline):
    model = CardDetails
    extra = 0
    max_num = 1


class SealedProductDetailsInline(admin.StackedInline):
    model = SealedProductDetails
    extra = 0
    max_num = 1


@admin.register(PokemonExtension)
class PokemonExtensionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "series", "release_date", "card_count")
    search_fields = ("code", "name")
    list_filter = ("series",)


@admin.register(Collectible)
class CollectibleAdmin(admin.ModelAdmin):
    list_display = ("display_name", "kind", "extension")
    list_filter = ("kind", "extension__series")
    search_fields = ("name", "extension__name", "extension__code")

    def get_inlines(self, request, obj):
        if not obj:
            return []
        if obj.kind == "CARD":
            return [CardDetailsInline]
        return [SealedProductDetailsInline]


@admin.register(OwnedLot)
class OwnedLotAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "user",
        "language",
        "state_label",
        "is_graded",
        "remaining_quantity",
        "average_unit_cost",
        "realized_pnl_total",
    )
    list_filter = ("collectible__kind", "language", "is_graded", "card_condition", "sealed_condition")
    search_fields = ("collectible__name", "user__username", "platform", "grading_grade")


@admin.register(CollectionOperation)
class CollectionOperationAdmin(admin.ModelAdmin):
    list_display = ("operation_date", "operation_type", "lot", "quantity", "unit_price", "total_price", "realized_pnl")
    list_filter = ("operation_type", "lot__collectible__kind", "lot__is_graded")
    search_fields = ("lot__collectible__name", "platform", "comment")


@admin.register(CollectibleValuation)
class CollectibleValuationAdmin(admin.ModelAdmin):
    list_display = (
        "collectible",
        "kind",
        "language",
        "state_label",
        "unit_value",
        "valued_at",
        "source_type",
    )
    list_filter = ("kind", "language", "is_graded", "card_condition", "sealed_condition", "source_type")
    search_fields = ("collectible__name", "grading_grade")
