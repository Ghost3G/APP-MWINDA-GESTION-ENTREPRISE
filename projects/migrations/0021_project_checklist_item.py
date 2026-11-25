from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0020_project_status_paint_pose'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectChecklistItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=80)),
                ('label', models.CharField(max_length=160)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('is_done', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                (
                    'completed_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='completed_project_checklist_items',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='checklist_items',
                        to='projects.project',
                    ),
                ),
            ],
            options={
                'ordering': ('order', 'id'),
                'unique_together': {('project', 'key')},
            },
        ),
    ]
