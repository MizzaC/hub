from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from PokeBoard.models import PokemonExtension, PokemonSeries


class Command(BaseCommand):
    help = "Charge le referentiel local des series et extensions Pokemon depuis un fichier JSON versionne."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default="",
            help="Chemin vers un JSON alternatif. Par defaut, utilise PokeBoard/data/extensions_seed.json",
        )

    def handle(self, *args, **options):
        if options["path"]:
            seed_path = Path(options["path"])
        else:
            seed_path = Path(__file__).resolve().parents[2] / "data" / "extensions_seed.json"

        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        series_count = 0
        extension_count = 0

        for series_data in payload.get("series", []):
            series, _ = PokemonSeries.objects.update_or_create(
                name=series_data["name"],
                defaults={
                    "era_order": series_data.get("era_order", 0),
                    "source_url": series_data.get("source_url", ""),
                },
            )
            series_count += 1

            for extension_data in series_data.get("extensions", []):
                PokemonExtension.objects.update_or_create(
                    code=extension_data["code"],
                    defaults={
                        "series": series,
                        "name": extension_data["name"],
                        "release_date": extension_data.get("release_date"),
                        "card_count": extension_data.get("card_count"),
                        "source_url": extension_data.get("source_url", series.source_url),
                    },
                )
                extension_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Referentiel charge: {series_count} series et {extension_count} extensions depuis {seed_path}"
            )
        )

