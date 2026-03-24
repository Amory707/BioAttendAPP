from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from accounts.models import Role, RoleUtilisateur
from django.contrib.auth.models import Permission


class Command(BaseCommand):
    help = "Clear user permissions and groups, remove all groups, and apply is_staff based on roles."

    def handle(self, *args, **options):
        User = get_user_model()

        # Remove all groups (start from zero)
        Group.objects.all().delete()

        # Clear user-specific permissions and group memberships, reset is_staff
        # Preserve superusers: do not clear their permissions/groups or unset is_staff
        for u in User.objects.all():
            if u.is_superuser:
                continue
            u.user_permissions.clear()
            u.groups.clear()
            u.is_staff = False
            u.save(update_fields=['is_staff'])

        # Grant is_staff to users having role 'admindjango' (case-insensitive)
        user_ids = RoleUtilisateur.objects.filter(role__nom__iexact='admindjango').values_list('utilisateur_id', flat=True)
        if user_ids:
            adm_users = User.objects.filter(id__in=user_ids)
            adm_users.update(is_staff=True)
            # Grant all model permissions to admindjango users so they can use admin site
            all_perms = list(Permission.objects.all())
            for u in adm_users:
                u.user_permissions.set(all_perms)
                u.save(update_fields=[])

        self.stdout.write(self.style.SUCCESS('Reset permissions: groups deleted, user permissions cleared, is_staff set for admindjango.'))
