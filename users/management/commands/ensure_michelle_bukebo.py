"""
Crée / met à jour le compte Michelle Bukebo (Responsable Commercial).

Usage Render Shell :
  python manage.py ensure_michelle_bukebo
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from users.permissions import COMMERCIAL_LEAD_USERNAME

User = get_user_model()

DEFAULT_PASSWORD = 'Bukebo2026'


class Command(BaseCommand):
    help = "Assure le compte michelle.bukebo (Responsable Commercial, sans Finance)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default=DEFAULT_PASSWORD,
            help='Mot de passe initial (uniquement si le compte est créé).',
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Réécrit le mot de passe même si le compte existe.',
        )

    def handle(self, *args, **options):
        password = options['password']
        reset = options['reset_password']

        defaults = {
            'email': 'michelle.bukebo@agencemwinda.com',
            'first_name': 'Michelle',
            'last_name': 'Bukebo',
            'role': 'directeur',
            'org_group': 'commercial',
            'direction': 'branding',
            'job_title': 'Responsable Commercial',
            'grade': 'RESPONSABLE COMMERCIAL',
            'department_name': 'Direction Commercial',
            'is_staff': False,
            'is_superuser': False,
        }

        user, created = User.objects.get_or_create(
            username=COMMERCIAL_LEAD_USERNAME,
            defaults=defaults,
        )

        changed = False
        for field, value in defaults.items():
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True

        if created or reset:
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte créé : {user.username} / mdp initial : {password}'
            ))
        elif reset:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte mis à jour + mot de passe réinitialisé : {user.username}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte déjà présent / synchronisé : {user.get_labeled_name()} ({user.username})'
            ))

        self.stdout.write(
            'Accès : direction (tous modules) sauf Finance. '
            'Notifiée à chaque projet avec agent commercial.'
        )
