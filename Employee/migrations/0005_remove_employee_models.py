# Suppression des modèles dupliqués de l'app Employee.
# Les données sont désormais gérées dans accounts, attendance et alerts.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Employee', '0004_utilisateur_photo_alter_utilisateur_embedding_facial'),
    ]

    operations = [
        migrations.DeleteModel(name='Alerte'),
        migrations.DeleteModel(name='Pointage'),
        migrations.DeleteModel(name='Utilisateur'),
        migrations.DeleteModel(name='Role'),
    ]
