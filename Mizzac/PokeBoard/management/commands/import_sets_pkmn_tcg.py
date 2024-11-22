# PokeBoard/management/commands/import_sets_pkmn_tcg.py

from django.core.management.base import BaseCommand
from pokemontcgsdk import Set as APISeries
from PokeBoard.models import Serie, Extension, Collection

class Command(BaseCommand):
    help = 'Importe les séries et extensions depuis l\'API Pokémon TCG'

    def handle(self, *args, **options):
        # Obtenir ou créer la Collection pour les cartes physiques du TCG
        collection, created = Collection.objects.get_or_create(
            name='Pokémon TCG Cartes Physiques',
            defaults={
                'description': 'Collection de cartes physiques du Pokémon TCG',
                'collection_type': 'physical',
                'image_url': '',  # Ajouter une URL d'image si disponible
            }
        )

        api_series_list = APISeries.all()
        for api_set in api_series_list:
            # Créer ou obtenir la Serie
            serie, created = Serie.objects.get_or_create(
                name=api_set.series,
                collection=collection,
                defaults={
                    'description': api_set.series,
                    'image_url': '',  # Ajouter une URL d'image si disponible
                }
            )

            # Créer ou obtenir l'Extension
            extension, created = Extension.objects.get_or_create(
                name=api_set.name,
                serie=serie,
                defaults={
                    'description': api_set.releaseDate,
                    'image_url': api_set.images.logo if hasattr(api_set.images, 'logo') else '',
                    'set_id': api_set.id,  # Stocker l'ID du set
                }
            )

            self.stdout.write(self.style.SUCCESS(f'Importé : {extension.name}'))
