"""
Déconnexion automatique à minuit (00:00, Africa/Kinshasa) — tous les utilisateurs.

Clôture la présence de la veille et invalide toutes les sessions Django,
même sans activité sur l'application.

Usage :
  python manage.py close_midnight_sessions
  python manage.py close_midnight_sessions --date 2026-08-10

Planification Render (cron) : 0 23 * * *  (= minuit Kinshasa, UTC+1)
"""
from django.core.management.base import BaseCommand

from users.presence import MIDNIGHT_LOGOUT_LABEL, parse_presence_date, run_midnight_logout_cycle


class Command(BaseCommand):
    help = (
        'Déconnecte tout le monde à minuit : clôture présence + invalidation sessions Django.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default='',
            help='Jour calendaire à clôturer (YYYY-MM-DD). Défaut : la veille.',
        )

    def handle(self, *args, **options):
        raw = (options.get('date') or '').strip()
        day = parse_presence_date(raw) if raw else None
        result = run_midnight_logout_cycle(day=day)
        self.stdout.write(self.style.SUCCESS(
            f'[OK] Minuit ({MIDNIGHT_LOGOUT_LABEL}) — jour {result["day"]} : '
            f'{result["presence_closed"]} fiche(s) présence clôturée(s), '
            f'{result["sessions_flushed"]} session(s) Django invalidée(s).'
        ))
