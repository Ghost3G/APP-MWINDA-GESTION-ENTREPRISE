from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0003_projectassignmentnotification'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('department', models.CharField(max_length=50)),
                ('status', models.CharField(choices=[('pending', 'À faire'), ('in_progress', 'En cours'), ('done', 'Terminé')], default='pending', max_length=20)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_tasks', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tasks', to='projects.project')),
            ],
            options={
                'ordering': ('project_id', 'order', 'id'),
            },
        ),
        migrations.AddIndex(
            model_name='projecttask',
            index=models.Index(fields=['assigned_to', 'status'], name='projects_pr_assigne_0f0f0f_idx'),
        ),
        migrations.AddIndex(
            model_name='projecttask',
            index=models.Index(fields=['department', 'status'], name='projects_pr_departm_1a1a1a_idx'),
        ),
    ]
