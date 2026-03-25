from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import Role, RoleUtilisateur
from django.contrib.auth.models import Permission


class Command(BaseCommand):
    """
    Commande de maintenance pour réinitialiser et synchroniser les permissions.
    
    CE QUE FAIT CETTE COMMANDE :
    1. Supprime TOUS les groupes existants dans la base de données.
    2. Réinitialise les permissions et l'accès 'is_staff' pour tous les utilisateurs 
       (sauf les super-utilisateurs).
    3. Identifie les utilisateurs ayant le rôle 'admindjango' et leur accorde :
        - L'accès à l'interface d'administration (is_staff = True).
        - La totalité des permissions disponibles dans le système.

    UTILISATION :
    python manage.py reset_permissions
    """
    help = "Clear user permissions and groups, remove all groups, and apply is_staff based on roles."

    def handle(self, *args, **options):
        User = get_user_model()

        Group.objects.all().delete()

        for u in User.objects.all():
            if u.is_superuser:
                continue
            u.user_permissions.clear()
            u.groups.clear()
            u.is_staff = False
            u.save(update_fields=['is_staff'])

        user_ids = RoleUtilisateur.objects.filter(role__nom__iexact='admindjango').values_list('utilisateur_id', flat=True)
        if user_ids:
            adm_users = User.objects.filter(id__in=user_ids)
            adm_users.update(is_staff=True)
            all_perms = list(Permission.objects.all())
            for u in adm_users:
                u.user_permissions.set(all_perms)
                u.save(update_fields=[])

        self.stdout.write(self.style.SUCCESS('Reset permissions: groups deleted, user permissions cleared, is_staff set for admindjango.'))
