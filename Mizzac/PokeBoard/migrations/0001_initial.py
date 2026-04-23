# Generated manually for PokeBoard initial schema.

from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PokemonSeries",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(blank=True, max_length=140, unique=True)),
                ("era_order", models.PositiveIntegerField(default=0)),
                ("source_url", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Serie Pokemon",
                "verbose_name_plural": "Series Pokemon",
                "ordering": ["era_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="PokemonExtension",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("release_date", models.DateField(blank=True, null=True)),
                ("card_count", models.PositiveIntegerField(blank=True, null=True)),
                ("source_url", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "series",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="extensions",
                        to="PokeBoard.pokemonseries",
                    ),
                ),
            ],
            options={
                "verbose_name": "Extension Pokemon",
                "verbose_name_plural": "Extensions Pokemon",
                "ordering": ["series__era_order", "release_date", "name"],
            },
        ),
        migrations.CreateModel(
            name="Collectible",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("CARD", "Carte"), ("SEALED", "Produit scelle")], max_length=10)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "extension",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collectibles",
                        to="PokeBoard.pokemonextension",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item catalogue",
                "verbose_name_plural": "Items catalogue",
                "ordering": ["extension__series__era_order", "extension__name", "name"],
            },
        ),
        migrations.CreateModel(
            name="CardDetails",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("card_number", models.CharField(blank=True, max_length=40)),
                ("rarity", models.CharField(blank=True, max_length=80)),
                ("variant", models.CharField(blank=True, max_length=80)),
                ("language", models.CharField(default="FR", max_length=30)),
                (
                    "collectible",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="card_details",
                        to="PokeBoard.collectible",
                    ),
                ),
            ],
            options={
                "verbose_name": "Detail carte",
                "verbose_name_plural": "Details cartes",
            },
        ),
        migrations.CreateModel(
            name="SealedProductDetails",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "product_type",
                    models.CharField(
                        choices=[
                            ("BOOSTER", "Booster"),
                            ("BUNDLE", "Bundle"),
                            ("DISPLAY", "Display"),
                            ("ETB", "Elite Trainer Box"),
                            ("TIN", "Tin"),
                            ("BOX", "Coffret"),
                            ("OTHER", "Autre"),
                        ],
                        default="OTHER",
                        max_length=20,
                    ),
                ),
                (
                    "collectible",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sealed_details",
                        to="PokeBoard.collectible",
                    ),
                ),
            ],
            options={
                "verbose_name": "Detail produit scelle",
                "verbose_name_plural": "Details produits scelles",
            },
        ),
        migrations.CreateModel(
            name="OwnedLot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("condition", models.CharField(choices=[("MINT", "Mint"), ("NM", "Near Mint"), ("EX", "Excellent"), ("GD", "Good"), ("LP", "Light Played"), ("POOR", "Poor")], default="NM", max_length=10)),
                ("platform", models.CharField(blank=True, max_length=120)),
                ("custom_description", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("remaining_quantity", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=14)),
                ("acquisition_total", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("average_unit_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("realized_pnl_total", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collectible",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lots",
                        to="PokeBoard.collectible",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pokemon_lots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Lot possede",
                "verbose_name_plural": "Lots possedes",
                "ordering": ["collectible__name", "created_at"],
            },
        ),
        migrations.CreateModel(
            name="CollectionOperation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_type", models.CharField(choices=[("BUY", "Achat"), ("SELL", "Vente"), ("ADD", "Ajout manuel"), ("ADJUST", "Correction")], max_length=10)),
                ("operation_date", models.DateField(default=django.utils.timezone.now)),
                ("quantity", models.DecimalField(decimal_places=4, max_digits=14)),
                ("unit_price", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("total_price", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("fees", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=14)),
                ("platform", models.CharField(blank=True, max_length=120)),
                ("comment", models.TextField(blank=True)),
                ("realized_pnl", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="operations",
                        to="PokeBoard.ownedlot",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pokemon_operations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Operation de collection",
                "verbose_name_plural": "Operations de collection",
                "ordering": ["-operation_date", "-id"],
            },
        ),
        migrations.CreateModel(
            name="CollectibleValuation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("condition", models.CharField(choices=[("MINT", "Mint"), ("NM", "Near Mint"), ("EX", "Excellent"), ("GD", "Good"), ("LP", "Light Played"), ("POOR", "Poor")], max_length=10)),
                ("unit_value", models.DecimalField(decimal_places=2, max_digits=14)),
                ("valued_at", models.DateField(default=django.utils.timezone.now)),
                ("source_type", models.CharField(choices=[("MANUAL", "Manuelle"), ("IMPORT", "Import"), ("API", "API")], default="MANUAL", max_length=10)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collectible",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="valuations",
                        to="PokeBoard.collectible",
                    ),
                ),
            ],
            options={
                "verbose_name": "Valorisation",
                "verbose_name_plural": "Valorisations",
                "ordering": ["-valued_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="pokemonextension",
            constraint=models.UniqueConstraint(fields=("series", "name"), name="pokeboard_extension_series_name_uniq"),
        ),
        migrations.AddConstraint(
            model_name="collectionoperation",
            constraint=models.CheckConstraint(
                check=models.Q(operation_type="ADJUST") | models.Q(quantity__gt=0),
                name="pokeboard_operation_non_adjust_positive_quantity",
            ),
        ),
        migrations.AddConstraint(
            model_name="collectiblevaluation",
            constraint=models.UniqueConstraint(
                fields=("collectible", "condition", "valued_at", "source_type"),
                name="pokeboard_valuation_unique_entry",
            ),
        ),
        migrations.AddIndex(
            model_name="pokemonextension",
            index=models.Index(fields=["series", "name"], name="PokeBoard_p_series__877793_idx"),
        ),
        migrations.AddIndex(
            model_name="pokemonextension",
            index=models.Index(fields=["code"], name="PokeBoard_p_code_98db6c_idx"),
        ),
        migrations.AddIndex(
            model_name="collectible",
            index=models.Index(fields=["extension", "kind"], name="PokeBoard_c_extensi_ae27ab_idx"),
        ),
        migrations.AddIndex(
            model_name="collectible",
            index=models.Index(fields=["name"], name="PokeBoard_c_name_339940_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "collectible"], name="PokeBoard_o_user_id_3b8e89_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "condition"], name="PokeBoard_o_user_id_013f29_idx"),
        ),
        migrations.AddIndex(
            model_name="ownedlot",
            index=models.Index(fields=["user", "platform"], name="PokeBoard_o_user_id_b6e56a_idx"),
        ),
        migrations.AddIndex(
            model_name="collectionoperation",
            index=models.Index(fields=["user", "operation_date"], name="PokeBoard_c_user_id_767054_idx"),
        ),
        migrations.AddIndex(
            model_name="collectionoperation",
            index=models.Index(fields=["lot", "operation_date"], name="PokeBoard_c_lot_id_b2fb57_idx"),
        ),
        migrations.AddIndex(
            model_name="collectionoperation",
            index=models.Index(fields=["operation_type"], name="PokeBoard_c_operati_340525_idx"),
        ),
        migrations.AddIndex(
            model_name="collectiblevaluation",
            index=models.Index(fields=["collectible", "condition", "valued_at"], name="PokeBoard_c_collect_8b333b_idx"),
        ),
    ]
