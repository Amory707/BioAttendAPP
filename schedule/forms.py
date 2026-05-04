from django import forms

from accounts.models import Utilisateur

from .models import ScheduleRequest, ScheduleSettings
from .services import get_employee_queryset


class ScheduleSettingsForm(forms.ModelForm):
    class Meta:
        model = ScheduleSettings
        fields = [
            'arrival_window_start',
            'arrival_window_end',
            'departure_window_start',
            'departure_window_end',
            'required_daily_minutes',
        ]
        widgets = {
            'arrival_window_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'arrival_window_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'departure_window_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'departure_window_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'required_daily_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
        labels = {
            'arrival_window_start': 'Arrivée dès',
            'arrival_window_end': 'Retard après',
            'departure_window_start': 'Départ anticipé avant',
            'departure_window_end': 'Journée clôturée à',
            'required_daily_minutes': 'Minutes obligatoires / jour',
        }


class ScheduleRequestForm(forms.ModelForm):
    class Meta:
        model = ScheduleRequest
        fields = ['utilisateur', 'start_at', 'end_at', 'category', 'description']
        widgets = {
            'start_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description optionnelle'}),
        }
        labels = {
            'utilisateur': 'Employé',
            'start_at': 'Début',
            'end_at': 'Fin',
            'category': 'Raison',
            'description': 'Description',
        }

    def __init__(self, *args, actor=None, is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.is_admin = is_admin
        self.fields['utilisateur'].queryset = get_employee_queryset()
        self.fields['utilisateur'].label_from_instance = lambda user: user.get_full_name() or user.username
        
        # Filtrer les choix de catégorie selon l'espace actif
        if is_admin:
            # En vue RH : toutes les catégories sauf RETARD
            self.fields['category'].choices = [
                (ScheduleRequest.CATEGORY_CONGE, 'Congé'),
                (ScheduleRequest.CATEGORY_MALADIE, 'Maladie'),
                (ScheduleRequest.CATEGORY_AUTRE, 'Autre'),
            ]
        else:
            # En vue employé : seulement Congé et Autre, pas Maladie
            self.fields['category'].choices = [
                (ScheduleRequest.CATEGORY_CONGE, 'Congé'),
                (ScheduleRequest.CATEGORY_AUTRE, 'Autre'),
            ]

        self.fields['start_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_at'].input_formats = ['%Y-%m-%dT%H:%M']

        if not is_admin:
            self.fields['utilisateur'].widget = forms.HiddenInput()
            self.fields['utilisateur'].required = False

    def clean_utilisateur(self):
        utilisateur = self.cleaned_data.get('utilisateur')
        if self.is_admin:
            if utilisateur is None:
                raise forms.ValidationError("Sélectionnez un employé.")
            return utilisateur

        if not isinstance(self.actor, Utilisateur):
            raise forms.ValidationError("Utilisateur invalide.")
        return self.actor

    def clean_category(self):
        category = self.cleaned_data.get('category')
        # Récupérer les choix valides selon le mode (admin ou employé)
        allowed_values = {value for value, _ in self.fields['category'].choices}
        if category not in allowed_values:
            raise forms.ValidationError("Cette raison ne peut pas être encodée.")
        return category
