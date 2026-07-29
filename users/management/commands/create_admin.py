from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Assure qu'un compte admin existe. "
        "Ne réécrit PAS le mot de passe d'un admin déjà présent "
        "(sauf avec --force), pour ne pas casser les mises à jour Render."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default=os.environ.get('ADMIN_USERNAME', 'admin'),
        )
        parser.add_argument(
            '--email',
            type=str,
            default=os.environ.get('ADMIN_EMAIL', 'admin@appmwinda.com'),
        )
        parser.add_argument(
            '--password',
            type=str,
            default=os.environ.get('ADMIN_PASSWORD', ''),
        )
        parser.add_argument(
            '--role',
            type=str,
            default='admin',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la mise à jour du mot de passe même si le compte existe déjà.',
        )

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        role = options['role']
        force = options['force']

        user = User.objects.filter(username=username).first()
        if user and not force:
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Admin "{username}" déjà présent — mot de passe conservé (safe pour les redeploys).'
                )
            )
            return

        if not password:
            if user and force:
                self.stdout.write(self.style.ERROR('[ERROR] --force nécessite ADMIN_PASSWORD / --password'))
                return
            self.stdout.write(
                self.style.WARNING(
                    '[SKIP] Aucun ADMIN_PASSWORD défini et aucun admin à créer. '
                    'Créez un admin manuellement si besoin.'
                )
            )
            return

        # Direction valide par défaut (branche atelier)
        direction = 'metal_design'
        if hasattr(User, 'DIRECTION_CHOICES'):
            valid = [value for value, _ in User.DIRECTION_CHOICES]
            if direction not in valid and valid:
                direction = valid[0]

        if user and force:
            user.email = email
            user.is_staff = True
            user.is_superuser = True
            user.role = role
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'[OK] Admin "{username}" mis à jour (--force).'))
            return

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            direction=direction,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save()
        self.stdout.write(self.style.SUCCESS(f'[OK] Admin "{username}" créé.'))
