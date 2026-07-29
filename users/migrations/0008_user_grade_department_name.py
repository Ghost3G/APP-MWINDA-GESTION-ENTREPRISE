from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_user_job_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='department_name',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name='user',
            name='grade',
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
