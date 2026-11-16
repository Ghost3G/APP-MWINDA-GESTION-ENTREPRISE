"""Alias rétrocompatibilité → ensure_bastin_musila (correction du prénom)."""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Alias : utilisez ensure_bastin_musila (prénom corrigé Bastin)."

    def add_arguments(self, parser):
        parser.add_argument('--password', type=str, default=None)
        parser.add_argument('--reset-password', action='store_true')

    def handle(self, *args, **options):
        kwargs = {}
        if options.get('password'):
            kwargs['password'] = options['password']
        if options.get('reset_password'):
            kwargs['reset_password'] = True
        self.stdout.write(self.style.WARNING(
            '[INFO] Correction du prénom : Bertin → Bastin. Lancement de ensure_bastin_musila…'
        ))
        call_command('ensure_bastin_musila', **kwargs)
