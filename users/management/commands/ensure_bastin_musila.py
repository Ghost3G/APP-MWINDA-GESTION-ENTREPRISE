"""
Crée / met à jour le compte Bastin Musila (DRH, administrateur tous accès).

Usage Render Shell :
  python manage.py ensure_bastin_musila
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

DEFAULT_USERNAME = 'bastin.musila'
LEGACY_USERNAME = 'bertin.musila'
DEFAULT_PASSWORD = 'Musila2026'


class Command(BaseCommand):
    help = "Assure le compte bastin.musila (DRH, admin, tous les accès)."

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
            'email': 'bastin.musila@agencemwinda.com',
            'first_name': 'Bastin',
            'last_name': 'Musila',
            'role': 'admin',
            'org_group': 'rh',
            'direction': 'metal_design',
            'job_title': 'DRH',
            'grade': 'DIRECTEUR RH',
            'department_name': 'Ressources Humaines',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        }

        # Corrige l’ancien identifiant bertin.musila si encore présent.
        legacy = User.objects.filter(username=LEGACY_USERNAME).first()
        user = User.objects.filter(username=DEFAULT_USERNAME).first()
        created = False

        if legacy and not user:
            legacy.username = DEFAULT_USERNAME
            for field, value in defaults.items():
                setattr(legacy, field, value)
            if reset:
                legacy.set_password(password)
            legacy.save()
            user = legacy
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte renommé {LEGACY_USERNAME} → {DEFAULT_USERNAME}'
            ))
        elif not user:
            user = User.objects.create_user(
                username=DEFAULT_USERNAME,
                password=password,
                **defaults,
            )
            created = True
        else:
            changed = False
            for field, value in defaults.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed = True
            if reset:
                user.set_password(password)
                changed = True
            if changed:
                user.save()
            if legacy and legacy.id != user.id:
                legacy.is_active = False
                legacy.save(update_fields=['is_active'])
                self.stdout.write(self.style.WARNING(
                    f'[INFO] Ancien compte {LEGACY_USERNAME} désactivé (doublon).'
                ))

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte créé : {user.username} / mdp initial : {password}'
            ))
        elif reset and not legacy:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte mis à jour + mot de passe réinitialisé : {user.username}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Compte déjà présent / synchronisé : {user.get_labeled_name()} ({user.username})'
            ))

        self.stdout.write('Accès : Administrateur / DRH (tous les modules).')
