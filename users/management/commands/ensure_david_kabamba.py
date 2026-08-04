"""
Crée / met à jour le compte David Kabamba (Architecte intérieur, agent Design).

Usage Render Shell :
  python manage.py ensure_david_kabamba
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEFAULT_USERNAME = 'david.kabamba'
DEFAULT_PASSWORD = 'Kabamba2026'


class Command(BaseCommand):
    help = "Assure le compte david.kabamba (Architecte intérieur, Design, accès agent)."

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
            'email': 'david.kabamba@agencemwinda.com',
            'first_name': 'David',
            'last_name': 'Kabamba',
            'role': 'agent',
            'org_group': 'design_communication',
            'direction': 'branding',
            'job_title': 'Architecte intérieur',
            'grade': 'AGENT',
            'department_name': 'Design et Communication',
            'is_staff': False,
            'is_superuser': False,
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

        self.stdout.write('Accès : Agent (département Design).')
