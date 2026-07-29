from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0006_taskattachment_taskchecklist_taskchecklistitem_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='commercial_agent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='commercial_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='project',
            name='technical_director',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='technical_director_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
