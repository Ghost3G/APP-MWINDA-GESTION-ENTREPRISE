"""
Crée / met à jour le compte Hans Kabasele (Comptable)
avec accès total direction.

Usage Render Shell :
  python manage.py ensure_hans_mangi
  python manage.py ensure_hans_mangi --reset-password
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

USERNAME = 'hans.mangi'
DEFAULT_PASSWORD = 'Mangi2026'


class Command(BaseCommand):
    help = "Assure le compte hans.mangi (Comptable, rang Directeurs, accès total)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default=DEFAULT_PASSWORD,
            help='Mot de passe initial (création ou --reset-password).',
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
            'email': 'hans.mangi@agencemwinda.com',
            'first_name': 'Hans',
            'last_name': 'Kabasele',
            'role': 'directeur',
            'org_group': 'direction',
            'direction': 'design_rd_innovation',
            'job_title': 'Comptable',
            'grade': 'COMPTABLE',
            'department_name': 'Direction Administratif et Financier',
            'is_staff': False,
            'is_superuser': False,
            'is_active': True,
        }

        user, created = User.objects.get_or_create(
            username=USERNAME,
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
                f'[OK] Compte synchronisé : {user.get_labeled_name()} ({user.username})'
            ))

        self.stdout.write(
            'Profil : Hans Kabasele / Comptable — rang Directeurs, accès total '
            '(modules direction + Finance).'
        )
