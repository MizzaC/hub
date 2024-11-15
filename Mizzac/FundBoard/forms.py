# FundBoard/forms.py

from django import forms
from .models import Abonnement, Revenu
from django.core.exceptions import ValidationError

class AbonnementForm(forms.ModelForm):
    class Meta:
        model = Abonnement
        fields = ['nom', 'montant', 'frequence', 'frequence_personnalisee', 'date_prochaine_echeance']
        widgets = {
            'date_prochaine_echeance': forms.DateInput(attrs={'type': 'date'}),
            'frequence_personnalisee': forms.NumberInput(attrs={'min': 1}),
        }

    def clean(self):
        cleaned_data = super().clean()
        frequence = cleaned_data.get('frequence')
        frequence_personnalisee = cleaned_data.get('frequence_personnalisee')

        if frequence == 'PERSONALIZED' and not frequence_personnalisee:
            self.add_error('frequence_personnalisee', "Veuillez spécifier le nombre de jours pour une fréquence personnalisée.")
        if frequence != 'PERSONALIZED' and frequence_personnalisee:
            self.add_error('frequence_personnalisee', "Ce champ doit être vide si la fréquence n'est pas personnalisée.")
