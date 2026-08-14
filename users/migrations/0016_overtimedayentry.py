from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0015_user_competency_profile'),
    ]

    operations = [
        migrations.CreateModel(
            name='OvertimeDayEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('work_date', models.DateField(db_index=True, verbose_name='Date prestée')),
                ('days', models.DecimalField(
                    decimal_places=2,
                    help_text='Ex. 1 = journée entière, 0.5 = demi-journée.',
                    max_digits=5,
                    verbose_name='Nombre de jours',
                )),
                ('notes', models.CharField(blank=True, max_length=500, verbose_name='Motif / notes')),
                ('source', models.CharField(
                    choices=[('manual', 'Saisie manuelle'), ('auto_validated', 'Validé depuis connexion')],
                    default='manual',
                    max_length=20,
                    verbose_name='Origine',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='overtime_entries_created',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Saisi par',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='overtime_entries',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Agent',
                )),
            ],
            options={
                'verbose_name': 'Jour supplémentaire',
                'verbose_name_plural': 'Jours supplémentaires',
                'ordering': ('-work_date', '-id'),
            },
        ),
        migrations.AddConstraint(
            model_name='overtimedayentry',
            constraint=models.UniqueConstraint(fields=('user', 'work_date'), name='unique_overtime_user_date'),
        ),
    ]
