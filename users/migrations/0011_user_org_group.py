from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_alter_user_direction'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='org_group',
            field=models.CharField(
                choices=[
                    ('direction', 'Direction'),
                    ('technique', 'Technique'),
                    ('finance', 'Finance'),
                    ('commercial', 'Commercial'),
                    ('logistique', 'Logistique'),
                    ('design_communication', 'Design et Communication'),
                    ('rd', 'Recherche et Développement'),
                ],
                default='technique',
                max_length=40,
            ),
        ),
    ]
