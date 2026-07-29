import datetime

from django.db import migrations, models
from django.utils import timezone


def backfill_created_at(apps, schema_editor):
    Project = apps.get_model('projects', 'Project')
    base = timezone.now() - datetime.timedelta(days=365)
    for index, project in enumerate(Project.objects.order_by('id')):
        # Conserve l'ordre d'entrée historique via l'id, ancré sur la date de début si possible
        if project.start_date:
            created = timezone.make_aware(
                datetime.datetime.combine(project.start_date, datetime.time(12, 0))
            ) + datetime.timedelta(seconds=index)
        else:
            created = base + datetime.timedelta(minutes=index)
        Project.objects.filter(pk=project.pk).update(created_at=created)


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0009_taskassignmentnotification'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True,
                db_index=True,
                default=timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AlterModelOptions(
            name='project',
            options={'ordering': ('created_at', 'id')},
        ),
        migrations.RunPython(backfill_created_at, migrations.RunPython.noop),
    ]
