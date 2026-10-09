from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0017_project_contract_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='in_distress',
            field=models.BooleanField(db_index=True, default=False, verbose_name='En souffrance'),
        ),
        migrations.AddField(
            model_name='project',
            name='distress_reason',
            field=models.TextField(blank=True, default='', verbose_name='Pourquoi en souffrance'),
        ),
        migrations.AddField(
            model_name='project',
            name='distress_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='distress_updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='distress_marks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
