from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('alerts', '0006_remove_alerte_statut'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='alerte',
            index=models.Index(fields=['masquee', 'type', 'date_creation'], name='alerte_mask_type_time_idx'),
        ),
        migrations.AddIndex(
            model_name='alerte',
            index=models.Index(fields=['utilisateur', 'masquee', 'type', 'date_creation'], name='alerte_user_type_time_idx'),
        ),
    ]
