from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_technical_branches'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
