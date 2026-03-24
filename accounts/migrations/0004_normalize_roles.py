from django.db import migrations


def forwards(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    # Map legacy role names to canonical lowercase values.
    # If a target role already exists, reassign relations and delete the old role
    RoleUtilisateur = apps.get_model('accounts', 'RoleUtilisateur')
    mapping = {
        'EMPLOYE': 'employé',
        'EMPLOYEE': 'employé',
        'ADMIN': 'admin',
        'ADMINDJANGO': 'admindjango',
    }
    for old, new in mapping.items():
        # find all roles matching the old name (case-insensitive)
        olds = list(Role.objects.filter(nom__iexact=old))
        if not olds:
            continue
        target = Role.objects.filter(nom__iexact=new).first()
        if target:
            # reassign relations from each old role to target, then delete old
            for old_role in olds:
                if old_role.id == target.id:
                    continue
                RoleUtilisateur.objects.filter(role_id=old_role.id).update(role_id=target.id)
                old_role.delete()
        else:
            # update the first old role to new value, and reassign/delete the rest
            first_old = olds[0]
            first_old.nom = new
            first_old.save()
            for old_role in olds[1:]:
                RoleUtilisateur.objects.filter(role_id=old_role.id).update(role_id=first_old.id)
                old_role.delete()


def backwards(apps, schema_editor):
    # no-op (don't revert normalization)
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_alter_role_nom'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
