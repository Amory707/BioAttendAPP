from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0005_alter_alerte_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='alerte',
            name='statut',
        ),
    ]
