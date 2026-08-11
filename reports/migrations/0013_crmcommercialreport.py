# Generated manually for CrmCommercialReport

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0016_sprint5_crm_finance'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reports', '0012_backfill_client_codes'),
    ]

    operations = [
        migrations.CreateModel(
            name='CrmCommercialReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_date', models.DateField(db_index=True, verbose_name='Date de l’activité')),
                ('activity_type', models.CharField(
                    choices=[
                        ('visit', 'Visite client'),
                        ('call', 'Appel téléphonique'),
                        ('meeting', 'Réunion / RDV'),
                        ('email', 'Email'),
                        ('quote_followup', 'Relance devis'),
                        ('payment_followup', 'Relance paiement'),
                        ('prospecting', 'Prospection'),
                        ('other', 'Autre'),
                    ],
                    default='call',
                    max_length=30,
                    verbose_name='Type d’activité',
                )),
                ('summary', models.TextField(verbose_name='Compte rendu')),
                ('result', models.CharField(
                    choices=[
                        ('quote_requested', 'Devis demandé'),
                        ('payment_promised', 'Paiement promis'),
                        ('won', 'Affaire conclue'),
                        ('lost', 'Refus / perdu'),
                        ('waiting', 'En attente'),
                        ('meeting_scheduled', 'RDV planifié'),
                        ('no_response', 'Pas de réponse'),
                        ('other', 'Autre'),
                    ],
                    default='waiting',
                    max_length=30,
                    verbose_name='Résultat',
                )),
                ('next_action', models.CharField(blank=True, max_length=255, verbose_name='Prochaine action')),
                ('next_action_date', models.DateField(blank=True, null=True, verbose_name='Date prochaine action')),
                ('quoted_amount', models.DecimalField(
                    blank=True,
                    decimal_places=2,
                    max_digits=12,
                    null=True,
                    verbose_name='Montant / devis évoqué ($)',
                )),
                ('attachment', models.FileField(blank=True, null=True, upload_to='crm_reports/%Y/%m/', verbose_name='Pièce jointe')),
                ('status', models.CharField(
                    choices=[('submitted', 'Soumis'), ('read', 'Lu par la direction')],
                    db_index=True,
                    default='submitted',
                    max_length=20,
                    verbose_name='Statut',
                )),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Lu le')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_commercial_reports',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Commercial',
                )),
                ('client', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commercial_reports',
                    to='reports.financeclient',
                    verbose_name='Client',
                )),
                ('project', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_commercial_reports',
                    to='projects.project',
                    verbose_name='Projet lié',
                )),
                ('read_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='crm_reports_marked_read',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Lu par',
                )),
            ],
            options={
                'verbose_name': 'Rapport commercial CRM',
                'verbose_name_plural': 'Rapports commerciaux CRM',
                'ordering': ('-activity_date', '-created_at'),
            },
        ),
    ]
