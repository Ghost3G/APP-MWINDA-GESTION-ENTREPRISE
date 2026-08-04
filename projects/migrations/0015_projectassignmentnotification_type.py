# Generated manually for delivery notifications to logistics

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0014_project_status_awaiting_delivery'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectassignmentnotification',
            name='notification_type',
            field=models.CharField(
                choices=[('assignment', 'Affectation'), ('delivery', 'Livraison')],
                db_index=True,
                default='assignment',
                max_length=20,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='projectassignmentnotification',
            unique_together={('user', 'project', 'notification_type')},
        ),
    ]
