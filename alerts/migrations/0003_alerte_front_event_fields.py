from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0002_alter_alerte_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="alerte",
            name="details",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="alerte",
            name="device_name",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="alerte",
            name="event_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ERROR", "ERROR"),
                    ("REJECTED", "REJECTED"),
                    ("BLOCKED", "BLOCKED"),
                ],
                max_length=20,
            ),
        ),
    ]
