from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('schedule', '0002_alter_schedulesettings_arrival_window_end_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='schedulerequest',
            index=models.Index(fields=['utilisateur', 'status', 'start_at', 'end_at'], name='sched_user_status_range_idx'),
        ),
        migrations.AddIndex(
            model_name='schedulerequest',
            index=models.Index(fields=['status', 'start_at', 'created_at'], name='sched_status_time_idx'),
        ),
    ]
