from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('projects', '0019_project_photo'),
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='city',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='supplier',
            name='contact_name',
            field=models.CharField(blank=True, max_length=120, verbose_name='Personne de contact'),
        ),
        migrations.AddField(
            model_name='supplier',
            name='lead_time_days',
            field=models.PositiveSmallIntegerField(default=0, help_text='Délai moyen de livraison en jours.'),
        ),
        migrations.AddField(
            model_name='supplier',
            name='payment_terms',
            field=models.CharField(blank=True, max_length=120, verbose_name='Conditions de paiement'),
        ),
        migrations.AddField(
            model_name='supplier',
            name='specialty',
            field=models.CharField(
                blank=True,
                choices=[
                    ('metal', 'Métal / soudure'),
                    ('wood', 'Bois / menuiserie'),
                    ('paint', 'Peinture / finition'),
                    ('plastic', 'Plexi / plastique'),
                    ('print', 'Impression / branding'),
                    ('transport', 'Transport / livraison'),
                    ('hardware', 'Quincaillerie'),
                    ('other', 'Autre'),
                ],
                default='other',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='DeliveryShipment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'À planifier'),
                        ('scheduled', 'Planifiée'),
                        ('in_transit', 'En route'),
                        ('delivered', 'Livrée'),
                        ('cancelled', 'Annulée'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('scheduled_date', models.DateField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('driver_name', models.CharField(blank=True, max_length=120)),
                ('recipient_name', models.CharField(blank=True, max_length=120)),
                ('destination', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_deliveries',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_shipments',
                    to='projects.project',
                )),
            ],
            options={
                'ordering': ['-scheduled_date', '-created_at', '-id'],
            },
        ),
    ]
