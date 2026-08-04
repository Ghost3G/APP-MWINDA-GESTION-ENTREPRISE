"""
Crée / met à jour le compte Michael Kabale (Chef Responsable Commercial).

Même personne que le DG (michael.ilunga), 2e rôle, même niveau d'accès.

Usage Render Shell :
  python manage.py ensure_michael_kabale
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEFAULT_USERNAME = 'michael.kabale'
DEFAULT_PASSWORD = 'Kabale2026'


class Command(BaseCommand):
    help = (
        "Assure le compte michael.kabale "
        "(Chef Responsable Commercial, même accès que le DG)."
    )

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
            'email': 'michael.kabale@agencemwinda.com',
            'first_name': 'Michael',
            'last_name': 'Kabale Ilunga',
            'role': 'admin',
            'org_group': 'commercial',
            'direction': 'branding',
            'job_title': 'Chef Responsable Commercial',
            'grade': 'CHEF RESPONSABLE COMMERCIAL',
            'department_name': 'Direction Commercial',
            'is_staff': True,
            'is_superuser': True,
        }

        user, created = User.objects.get_or_create(
            username=DEFAULT_USERNAME,
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
            'Rôle : Chef Responsable Commercial. '
            'Accès : même niveau que le DG (admin). '
            'Notifié à chaque projet avec agent commercial.'
        )
