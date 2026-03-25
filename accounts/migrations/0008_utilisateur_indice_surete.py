from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_merge_20260325_1020"),
    ]

    operations = [
        migrations.AddField(
            model_name="utilisateur",
            name="indice_surete",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
