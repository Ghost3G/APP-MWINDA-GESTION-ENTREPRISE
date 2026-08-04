# Generated manually for awaiting_delivery project status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0013_project_home_featured'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'En attente'),
                    ('progress', 'En cours'),
                    ('urgent', 'Urgence'),
                    ('awaiting_delivery', 'En attente de livraison'),
                    ('done', 'Terminé'),
                ],
                max_length=20,
            ),
        ),
    ]
