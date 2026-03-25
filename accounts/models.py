import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from pgvector.django import VectorField


class Utilisateur(AbstractUser):
    """
    Modèle UTILISATEUR selon le MLD
    Extend AbstractUser de Django pour l'authentification native
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    embedding_facial = VectorField(dimensions=384, null=True, blank=True)
    departement = models.CharField(max_length=50, blank=True, null=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(blank=True, null=True)
    
    roles = models.ManyToManyField(
        'Role',
        through='RoleUtilisateur',
        related_name='utilisateurs',
        blank=True,
    )

    class Meta:
        db_table = 'utilisateur'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username})"

    @property
    def is_admindjango(self):
        """Retourne True si l'utilisateur a le rôle 'admindjango' (insensible à la casse)."""
        return self.roles.filter(nom__iexact='acces_total').exists()

    @property
    def is_acces_total(self):
        """Retourne True si l'utilisateur a le rôle 'acces_total' (insensible à la casse)."""
        return self.roles.filter(nom__iexact='acces_total').exists()

    @property
    def is_employe(self):
        """Retourne True si l'utilisateur a le rôle 'employé' (insensible à la casse)."""
        return self.roles.filter(nom__iexact='employé').exists()


class Role(models.Model):
    """
    Modèle RÔLE selon le MLD
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(
        max_length=30,
        choices=[('employé', 'employé'), ('admin', 'admin'), ('acces_total', 'acces_total')],
        unique=True,
    )

    class Meta:
        db_table = 'role'

    def __str__(self):
        return self.nom


class RoleUtilisateur(models.Model):
    """
    Table associative RÔLE_UTILISATEUR selon le MLD
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='role_utilisateurs',
    )
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='role_utilisateurs',
    )

    class Meta:
        db_table = 'role_utilisateur'
        unique_together = ('role', 'utilisateur')

    def _sync_django_admin_access(self):
        has_django_admin_role = self.utilisateur.role_utilisateurs.filter(role__nom__iexact='acces_total').exists()
        desired_is_staff = self.utilisateur.is_superuser or has_django_admin_role

        if self.utilisateur.is_staff != desired_is_staff:
            self.utilisateur.is_staff = desired_is_staff
            self.utilisateur.save(update_fields=['is_staff'])

        try:
            from django.contrib.auth.models import Permission
        except Exception:
            Permission = None

        if not self.utilisateur.is_superuser and Permission is not None:
            if has_django_admin_role:
                perms = list(Permission.objects.all())
                self.utilisateur.user_permissions.set(perms)
            else:
                self.utilisateur.user_permissions.clear()

    def save(self, *args, **kwargs):
        try:
            from django.core.exceptions import PermissionDenied
            from .middleware import ThreadLocalMiddleware
        except Exception:
            ThreadLocalMiddleware = None
            PermissionDenied = None

        if self.role and self.role.nom.lower() == 'acces_total' and ThreadLocalMiddleware is not None:
            req = ThreadLocalMiddleware.get_current_request()
            if req is not None:
                user = getattr(req, 'user', None)
                if not (getattr(user, 'is_superuser', False) and getattr(user, 'username', '') == 'bioattend'):
                    raise PermissionDenied("Seulement 'bioattend' peut attribuer le rôle admindjango.")

        super().save(*args, **kwargs)
        self._sync_django_admin_access()

    def delete(self, *args, **kwargs):
        utilisateur = self.utilisateur
        super().delete(*args, **kwargs)
        has_django_admin_role = utilisateur.role_utilisateurs.filter(role__nom__iexact='admindjango').exists()
        desired_is_staff = utilisateur.is_superuser or has_django_admin_role

        if utilisateur.is_staff != desired_is_staff:
            utilisateur.is_staff = desired_is_staff
            utilisateur.save(update_fields=['is_staff'])

    def __str__(self):
        return f"{self.utilisateur} - {self.role}"
