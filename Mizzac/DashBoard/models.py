from django.db import models
from django.contrib.auth.models import User

class Dashboard(models.Model):
    utilisateur = models.OneToOneField(User, on_delete=models.CASCADE)
    configuration = models.JSONField(default=dict, blank=True, null=True)
    widgets = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return f"Dashboard de {self.utilisateur.username}"
    
    