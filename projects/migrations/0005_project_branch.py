from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0004_projecttask'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='branch',
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
    ]
