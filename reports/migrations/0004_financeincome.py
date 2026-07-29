from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0003_alter_dailyreport_department_financeexpense'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinanceIncome',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('income_date', models.DateField()),
                ('command_reference', models.CharField(max_length=120)),
                ('label', models.CharField(max_length=180)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='finance_incomes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-income_date', '-created_at'),
            },
        ),
    ]
