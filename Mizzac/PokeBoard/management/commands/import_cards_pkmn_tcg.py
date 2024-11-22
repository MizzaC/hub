# PokeBoard/management/commands/import_cards_pkmn_tcg.py

from django.core.management.base import BaseCommand
from pokemontcgsdk import Card as APICard
from PokeBoard.models import Card, Extension

class Command(BaseCommand):
    help = 'Importe les cartes depuis l\'API Pokémon TCG'

    def handle(self, *args, **options):
        extensions = Extension.objects.all()
        for extension in extensions:
            self.stdout.write(f'Importation des cartes pour : {extension.name}')
            if extension.set_id:
                api_cards = APICard.where(q=f'set.id:{extension.set_id}')
            else:
                api_cards = APICard.where(q=f'set.name:"{extension.name}"')
            for api_card in api_cards:
                card, created = Card.objects.get_or_create(
                    name=api_card.name,
                    card_number=api_card.number,
                    extension=extension,
                    defaults={
                        'rarity': api_card.rarity or '',
                        'image_url': api_card.images.large or '',
                    }
                )
            self.stdout.write(self.style.SUCCESS(f'Cartes importées pour : {extension.name}'))
