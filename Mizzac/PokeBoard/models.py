from django.db import models
from django.contrib.auth.models import User

class Collection(models.Model):
    COLLECTION_TYPES = [
        ('physical', 'Physique'),
        ('virtual', 'Virtuelle'),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    collection_type = models.CharField(max_length=10, choices=COLLECTION_TYPES)
    image_url = models.URLField(max_length=200, blank=True)

    def __str__(self):
        return self.name
    

class UserCollection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_collections')
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    cards = models.ManyToManyField('Card', through='UserCard', related_name='user_collections')

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Serie(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=200, blank=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Extension(models.Model):
    set_id = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    serie = models.ForeignKey(Serie, on_delete=models.CASCADE)
    image_url = models.URLField(max_length=200, blank=True)

    def __str__(self):
        return self.name

class Card(models.Model):
    name = models.CharField(max_length=255)
    card_number = models.CharField(max_length=50)
    rarity = models.CharField(max_length=50, blank=True)
    image_url = models.URLField(max_length=200, blank=True)
    extension = models.ForeignKey(Extension, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} ({self.card_number})"

class UserCard(models.Model):
    user_collection = models.ForeignKey(UserCollection, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('user_collection', 'card')

    def __str__(self):
        return f"{self.card.name} in {self.user_collection.name}"
