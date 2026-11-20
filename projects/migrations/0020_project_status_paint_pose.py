# Generated manually for awaiting_paint / awaiting_pose project statuses

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0019_project_photo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'En attente'),
                    ('awaiting_paint', 'En attente de peinture'),
                    ('awaiting_pose', 'En attente de la pose'),
                    ('progress', 'En cours'),
                    ('urgent', 'Urgence'),
                    ('awaiting_delivery', 'En attente de livraison'),
                    ('done', 'Terminé'),
                ],
                max_length=20,
            ),
        ),
    ]
