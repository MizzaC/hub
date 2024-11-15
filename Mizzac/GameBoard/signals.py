from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.text import slugify
from .models import Game

@receiver(pre_save, sender=Game)
def set_slug(sender, instance, **kwargs):
    if not instance.game_slug:
        instance.game_slug = slugify(instance.name)