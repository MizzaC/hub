# FundBoard/forms.py

from django import forms
from .models import Abonnement, Revenu, CompteBancaire, InvestmentAccount, Transaction, Asset, ListeSuivi, SuiviAsset
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

class ManualAccountForm(forms.ModelForm):
    class Meta:
        model  = CompteBancaire
        fields = ['nom', 'type_compte', 'solde']    # solde = facultatif (placeholder « 0 »)
        widgets = {
            'nom':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mon compte courant'}),
            'type_compte':forms.Select(attrs={'class': 'form-select'}),
            'solde':      forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': '0.01'}),
        }
        labels = {
            'nom':        'Nom du compte',
            'type_compte':'Type de compte',
            'solde':      'Solde initial (facultatif)',
        }
