from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_alter_pointage_utilisateur'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='pointage',
            index=models.Index(fields=['utilisateur', 'statut', 'horodatage'], name='point_user_stat_time_idx'),
        ),
        migrations.AddIndex(
            model_name='pointage',
            index=models.Index(fields=['utilisateur', 'origine', '-horodatage', '-id'], name='point_user_orig_time_idx'),
        ),
        migrations.AddIndex(
            model_name='pointage',
            index=models.Index(fields=['origine', 'statut', 'incident_type', 'horodatage'], name='point_security_time_idx'),
        ),
        migrations.AddIndex(
            model_name='pointage',
            index=models.Index(fields=['statut', 'horodatage'], name='point_stat_time_idx'),
        ),
    ]
