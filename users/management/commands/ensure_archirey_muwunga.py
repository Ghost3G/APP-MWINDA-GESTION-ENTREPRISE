"""
Crée / corrige le compte Archirey Muwunga
(Directeur Financier et Administratif).

Migre aussi l'ancien identifiant archirey.muhongaya si présent.

Usage Render Shell :
  python manage.py ensure_archirey_muwunga
  python manage.py ensure_archirey_muwunga --reset-password
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

USERNAME = 'archirey.muwunga'
LEGACY_USERNAMES = ('archirey.muhongaya', 'archirey.mowunga')
DEFAULT_PASSWORD = 'Muwunga2026'


class Command(BaseCommand):
    help = "Assure / corrige le compte archirey.muwunga (Directeur Financier et Administratif)."

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
            'email': 'archirey.muwunga@agencemwinda.com',
            'first_name': 'Archirey',
            'last_name': 'Muwunga',
            'role': 'directeur',
            'org_group': 'finance',
            'direction': 'design_rd_innovation',
            'job_title': 'Directeur Financier et Administratif',
            'grade': 'DIRECTEUR FINANCIER',
            'department_name': 'Direction Administratif et Financier',
            'is_staff': False,
            'is_superuser': False,
            'is_active': True,
        }

        user = User.objects.filter(username=USERNAME).first()
        renamed_from = None
        if user is None:
            for legacy in LEGACY_USERNAMES:
                legacy_user = User.objects.filter(username=legacy).first()
                if legacy_user:
                    user = legacy_user
                    renamed_from = legacy
                    break

        created = False
        if user is None:
            user = User(username=USERNAME)
            created = True
        elif renamed_from:
            user.username = USERNAME

        changed = created or bool(renamed_from)
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
        elif renamed_from:
            msg = f'[OK] Compte renommé {renamed_from} → {user.username} et corrigé'
            if reset:
                msg += f' (mdp : {password})'
            self.stdout.write(self.style.SUCCESS(msg))
        elif reset:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte mis à jour + mot de passe réinitialisé : {user.username}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte synchronisé : {user.get_labeled_name()} ({user.username})'
            ))

        self.stdout.write(
            'Profil : Archirey Muwunga / Directeur Financier et Administratif '
            '(département Finance, rôle directeur).'
        )
