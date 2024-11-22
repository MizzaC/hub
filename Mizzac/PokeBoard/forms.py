# forms.py

from django import forms
from .models import UserCollection

class UserCollectionForm(forms.ModelForm):
    class Meta:
        model = UserCollection
        fields = ['name', 'collection']
        widgets = {
            'collection': forms.RadioSelect,  # Permettre à l'utilisateur de choisir le type de collection
        }
