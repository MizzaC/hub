from django.conf import settings
from django.db import models
from django.utils.text import slugify


def get_upload_path(instance, filename):
    # Use the name of the game to make the directory name
    return f'GameBoard/Games/{instance.name}/{filename}'

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Game(models.Model):
    name = models.CharField(max_length=100, primary_key=True)
    description = models.JSONField(default=list, blank=True)
    rules = models.JSONField(default=list, blank=True)
    versions = models.JSONField(default=list, blank=True)
    tips = models.JSONField(default=list, blank=True)
    categories = models.ManyToManyField('Category', related_name='Game')
    cover = models.ImageField(upload_to=get_upload_path, default='GameBoard/Games/default.png')
    game_slug = models.SlugField(unique=True, blank=True)  # Champ slug ajouté

    def save(self, *args, **kwargs):
        if not self.game_slug:
            self.game_slug = slugify(self.name)  # Génère un slug basé sur le nom
        super(Game, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    guest_name = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.user.username if self.user else self.guest_name
    
class GamesStats(models.Model):
    id = models.AutoField(primary_key=True)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, null=False)
    game_version = models.CharField(max_length=100, blank=False) #Put Original if it's not a specific version
    date_time = models.DateTimeField(auto_now_add=True)
    game_stats = models.JSONField(default=dict, blank=False)
    
class SkyJoSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    scores = models.JSONField(default=dict, blank=False)
    ranking = models.JSONField(default=list, blank=True)
    save_slug = models.SlugField(unique=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.save_slug:
            self.save_slug = slugify(self.id)
        super(SkyJoSave, self).save(*args, **kwargs)

class NavalBattleSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    calling_shot = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of shot
    ranking = models.JSONField(default=list, blank=True)
    
    
class TicTacToeSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    users_actions = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of symbol
    ranking = models.JSONField(default=list, blank=True)
    
    
class ChessSave(models.Model):
    id = models.AutoField(primary_key=True)
    date_time = models.DateTimeField(auto_now_add=True)
    users = models.JSONField(default=dict, blank=False)
    game_grid = models.JSONField(default=list, blank=False)
    users_actions = models.JSONField(default=list, blank=False) # format : 1A2 first number identify player and second part identify the location of move
    ranking = models.JSONField(default=list, blank=True)
    
