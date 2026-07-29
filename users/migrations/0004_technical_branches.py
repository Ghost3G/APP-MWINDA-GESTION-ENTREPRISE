from django.db import migrations, models


def migrate_user_branches(apps, schema_editor):
    User = apps.get_model('users', 'User')
    mapping = {
        'design': 'wood_design',
        'marketing': 'branding',
        'finance': 'gravure',
        'technique': 'metal_design',
        'signalétique': 'signaletique',
    }
    valid = {
        'metal_design', 'wood_design', 'branding',
        'signaletique', 'gravure', 'design_rd_innovation',
    }
    for user in User.objects.all():
        if user.direction not in valid:
            user.direction = mapping.get(user.direction, 'metal_design')
            user.save(update_fields=['direction'])


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_user_groups_alter_user_user_permissions'),
        ('projects', '0005_project_branch'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='direction',
            field=models.CharField(
                choices=[
                    ('metal_design', 'Metal Design'),
                    ('wood_design', 'Wood Design'),
                    ('branding', 'Branding'),
                    ('signaletique', 'Signalétique'),
                    ('gravure', 'Gravure'),
                    ('design_rd_innovation', 'Design RD & Innovation'),
                ],
                default='metal_design',
                max_length=50,
            ),
        ),
        migrations.RunPython(migrate_user_branches, migrations.RunPython.noop),
    ]
