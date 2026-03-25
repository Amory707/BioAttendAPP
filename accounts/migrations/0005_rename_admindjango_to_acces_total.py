from django.db import migrations


def forwards(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RoleUtilisateur = apps.get_model('accounts', 'RoleUtilisateur')

    olds = list(Role.objects.filter(nom__iexact='admindjango'))
    if not olds:
        return
    target = Role.objects.filter(nom__iexact='acces_total').first()
    if target:
        for old in olds:
            if old.id == target.id:
                continue
            RoleUtilisateur.objects.filter(role_id=old.id).update(role_id=target.id)
            old.delete()
    else:
        first_old = olds[0]
        first_old.nom = 'acces_total'
        first_old.save()
        for old in olds[1:]:
            RoleUtilisateur.objects.filter(role_id=old.id).update(role_id=first_old.id)
            old.delete()


def backwards(apps, schema_editor):
    # don't revert
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_normalize_roles'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
