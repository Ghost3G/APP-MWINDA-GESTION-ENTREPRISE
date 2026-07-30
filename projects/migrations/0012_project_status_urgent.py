# Generated manually for urgent project status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0011_project_cover_image'),
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
                    ('done', 'Terminé'),
                ],
                max_length=20,
            ),
        ),
    ]
