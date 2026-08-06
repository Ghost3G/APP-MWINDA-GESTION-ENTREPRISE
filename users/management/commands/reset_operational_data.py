"""
Remet l'activité métier à zéro sans supprimer les comptes utilisateurs.

Conserve :
  - users.User (identifiants, mots de passe, rôles, départements…)

Efface :
  - projets, tâches, pièces jointes, checklists, commentaires, labels
  - heures de service / présence (AgentTimeEntry)
  - finance (dépenses / recettes)
  - rapports journaliers
  - messages
  - notifications d'affectation
  - tentatives de connexion & audit logs
  - sessions Django (reconnexion nécessaire)

Usage (Render Shell) :
  python manage.py reset_operational_data --confirm RESET
"""
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from messaging.models import Message
from projects.models import (
    AgentTimeEntry,
    Project,
    ProjectAssignmentNotification,
    ProjectTask,
    TaskAssignmentNotification,
    TaskAttachment,
    TaskChecklist,
    TaskChecklistItem,
    TaskComment,
    TaskLabel,
)
from reports.models import (
    CrmFollowUp,
    DailyReport,
    FinanceClient,
    FinanceDayClosure,
    FinanceExpense,
    FinanceIncome,
)
from users.models import AuditLog, LoginAttempt, User


class Command(BaseCommand):
    help = "Efface projets / heures / finance / rapports / messages. Conserve les comptes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            type=str,
            required=True,
            help='Doit être exactement : RESET',
        )

    def handle(self, *args, **options):
        if options['confirm'] != 'RESET':
            raise CommandError('Refusé. Relancez avec : --confirm RESET')

        users_before = User.objects.count()
        counts = {}

        with transaction.atomic():
            counts['task_assignment_notifications'] = TaskAssignmentNotification.objects.all().delete()[0]
            counts['project_assignment_notifications'] = ProjectAssignmentNotification.objects.all().delete()[0]
            counts['task_attachments'] = TaskAttachment.objects.all().delete()[0]
            counts['task_checklist_items'] = TaskChecklistItem.objects.all().delete()[0]
            counts['task_checklists'] = TaskChecklist.objects.all().delete()[0]
            counts['task_comments'] = TaskComment.objects.all().delete()[0]
            counts['project_tasks'] = ProjectTask.objects.all().delete()[0]
            counts['task_labels'] = TaskLabel.objects.all().delete()[0]
            counts['projects'] = Project.objects.all().delete()[0]
            counts['time_entries'] = AgentTimeEntry.objects.all().delete()[0]
            counts['messages'] = Message.objects.all().delete()[0]
            counts['daily_reports'] = DailyReport.objects.all().delete()[0]
            counts['finance_expenses'] = FinanceExpense.objects.all().delete()[0]
            counts['finance_incomes'] = FinanceIncome.objects.all().delete()[0]
            counts['finance_day_closures'] = FinanceDayClosure.objects.all().delete()[0]
            counts['crm_follow_ups'] = CrmFollowUp.objects.all().delete()[0]
            counts['finance_clients'] = FinanceClient.objects.all().delete()[0]
            counts['login_attempts'] = LoginAttempt.objects.all().delete()[0]
            counts['audit_logs'] = AuditLog.objects.all().delete()[0]
            counts['sessions'] = Session.objects.all().delete()[0]

        users_after = User.objects.count()
        if users_after != users_before:
            raise CommandError(
                f'Sécurité : nombre d’utilisateurs changé ({users_before} → {users_after}). Rollback attendu.'
            )

        self.stdout.write(self.style.WARNING('=== Remise à zéro opérationnelle ==='))
        for label, total in counts.items():
            self.stdout.write(f'  - {label}: {total}')
        self.stdout.write(self.style.SUCCESS(f'[OK] Comptes conservés : {users_after}'))
        self.stdout.write(self.style.SUCCESS('[OK] Application prête pour un démarrage à zéro.'))
