"""
Crée / met à jour le personnel MWINDA (seed_demo_data).

Usage Render (One-Off Job ou Shell) :
    ALLOW_DEMO_SEED=1 python manage.py seed_personnel
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée ou met à jour tous les comptes personnel MWINDA (+ projets démo)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Autorise le seed même si DEBUG=False (équivalent ALLOW_DEMO_SEED=1).',
        )

    def handle(self, *args, **options):
        allowed = (
            settings.DEBUG
            or options['force']
            or os.environ.get('ALLOW_DEMO_SEED', '').lower() in {'1', 'true', 'yes'}
        )
        if not allowed:
            raise CommandError(
                'Refusé en production. Relancez avec --force ou ALLOW_DEMO_SEED=1'
            )

        # seed_demo_data bloque aussi au import si prod sans ALLOW_DEMO_SEED
        os.environ['ALLOW_DEMO_SEED'] = '1'

        from seed_demo_data import main

        main()
        self.stdout.write(self.style.SUCCESS('[OK] Personnel MWINDA synchronisé.'))
