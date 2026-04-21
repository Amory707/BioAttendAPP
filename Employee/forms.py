import re
import unicodedata

from django import forms
from accounts.models import Role, RoleUtilisateur, Utilisateur


def _generate_username(first_name, last_name):
    """Génère un username unique depuis prénom+nom."""
    base = (first_name + last_name).lower()
    base = unicodedata.normalize('NFD', base)
    base = ''.join(c for c in base if unicodedata.category(c) != 'Mn')
    base = re.sub(r'[^a-z0-9]', '', base) or 'user'
    username = base
    counter = 1
    while Utilisateur.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    return username


class UtilisateurUnifiedForm(forms.ModelForm):
    """
    Formulaire unique pour la création ET la modification d'un employé.
    - Username auto-généré à la création (prénom+nom)
    - Rôle : sélection unique
    - Photo : optionnelle (enrôlement biométrique)
    - Mot de passe : présent à la création OU si editing_self
    - acces_total réservé au superuser
    """
    first_name = forms.CharField(required=True, label='Prénom', max_length=150)
    last_name = forms.CharField(required=True, label='Nom', max_length=150)
    email = forms.EmailField(required=True, label='Email')

    roles = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        widget=forms.RadioSelect,
        required=True,
        label='Rôle',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label='Mot de passe',
        help_text='Laissez vide pour conserver le mot de passe actuel.',
    )

    class Meta:
        model = Utilisateur
        fields = ['first_name', 'last_name', 'email', 'departement', 'date_debut', 'date_fin']
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Email',
            'departement': 'Département',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
        }
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, editing_self=True, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        is_create = self.instance is None or self.instance._state.adding

        if is_create or not editing_self:
            del self.fields['password']

        if request_user and request_user.is_superuser:
            roles_qs = Role.objects.all()
        else:
            roles_qs = Role.objects.exclude(nom__iexact='acces_total')
        self.fields['roles'].queryset = roles_qs
        self._manageable_role_pks = set(roles_qs.values_list('pk', flat=True))

        if not is_create:
            self.fields['roles'].initial = (
                self.instance.roles
                .filter(pk__in=self._manageable_role_pks)
                .order_by('nom')
                .first()
            )

    def clean(self):
        cleaned_data = super().clean()
        first = cleaned_data.get('first_name', '')
        last = cleaned_data.get('last_name', '')
        base = re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFD', (first + last).lower()))
        base = ''.join(c for c in base if unicodedata.category(c) != 'Mn')
        if not base:
            raise forms.ValidationError("Le prénom et le nom ne contiennent aucun caractère valide pour générer un identifiant.")
        return cleaned_data

    def clean_roles(self):
        # Reject crafted payloads that try to submit multiple roles in a single-value field.
        raw_roles = self.data.getlist('roles') if hasattr(self.data, 'getlist') else []
        if len([item for item in raw_roles if item]) > 1:
            raise forms.ValidationError("Un seul rôle peut être attribué lors de la création d'un employé.")

        role = self.cleaned_data.get('roles')
        if role is None:
            raise forms.ValidationError("Sélectionnez un rôle.")
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        is_create = self.instance is None or self.instance._state.adding

        if is_create:
            user.username = _generate_username(user.first_name, user.last_name)
            user.set_password(user.username)
        elif 'password' in self.fields:
            password = self.cleaned_data.get('password')
            if password:
                user.set_password(password)

        if commit:
            user.save()
            self.save_roles(user)
        return user

    def save_roles(self, user=None):
        user = user or self.instance
        if user is None or user.pk is None:
            return

        selected_role = self.cleaned_data.get('roles')
        RoleUtilisateur.objects.filter(
            utilisateur=user,
            role__pk__in=self._manageable_role_pks,
        ).delete()
        if selected_role is not None:
            RoleUtilisateur.objects.get_or_create(utilisateur=user, role=selected_role)
