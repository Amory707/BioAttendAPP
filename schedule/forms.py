from django import forms

from accounts.models import Utilisateur

from .models import ScheduleRequest
from .services import get_employee_queryset


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

        self.fields['start_at'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['end_at'].input_formats = ['%Y-%m-%dT%H:%M']

        if not is_admin:
            self.fields['utilisateur'].widget = forms.HiddenInput()
            self.fields['utilisateur'].required = False
            self.fields['category'].choices = [
                (ScheduleRequest.CATEGORY_RETARD, 'Retard'),
                (ScheduleRequest.CATEGORY_CONGE, 'Congé'),
                (ScheduleRequest.CATEGORY_AUTRE, 'Autre'),
            ]

    def clean_utilisateur(self):
        utilisateur = self.cleaned_data.get('utilisateur')
        if self.is_admin:
            if utilisateur is None:
                raise forms.ValidationError("Sélectionnez un employé.")
            return utilisateur

        if not isinstance(self.actor, Utilisateur):
            raise forms.ValidationError("Utilisateur invalide.")
        return self.actor
