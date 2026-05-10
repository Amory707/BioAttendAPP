from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Employee', '0005_remove_employee_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='BiometricSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singleton_guard', models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ('photo_similarity_threshold', models.FloatField(default=50.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Paramètre biométrique',
                'verbose_name_plural': 'Paramètres biométriques',
                'db_table': 'biometric_settings',
            },
        ),
    ]
