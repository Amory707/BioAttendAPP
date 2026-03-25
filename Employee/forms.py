from django import forms
from .models import Utilisateur


class UtilisateurForm(forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ['Login_Utilisateur', 'Nom', 'Prenom', 'Email', 'Mot_de_passe', 'Photo', 'Departement', 'Date_fin', 'roles']
        widgets = {
            'Mot_de_passe': forms.PasswordInput(render_value=True),
            'Date_fin': forms.DateInput(attrs={'type': 'date'}),
            'roles': forms.CheckboxSelectMultiple,
        }

    def clean(self):
        cleaned_data = super().clean()
        nom = cleaned_data.get('Nom')
        prenom = cleaned_data.get('Prenom')
        email = cleaned_data.get('Email')

        if not nom or not prenom or not email:
            raise forms.ValidationError("Nom, Prénom et Email sont requis.")

        return cleaned_data
