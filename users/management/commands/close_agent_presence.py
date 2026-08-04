"""
Clôture automatique des sessions agents à 17h30 (présence).

Usage :
  python manage.py close_agent_presence
  python manage.py close_agent_presence --date 2026-08-04
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.presence import (
    WORK_END_LABEL,
    WORK_START_LABEL,
    close_open_agent_sessions_for_day,
    parse_presence_date,
)


class Command(BaseCommand):
    help = (
        f'Ferme les sessions agents ouvertes à {WORK_END_LABEL} '
        f'(horaires {WORK_START_LABEL}-{WORK_END_LABEL}). Directeurs exclus.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            default='',
            help='Jour à clôturer (YYYY-MM-DD). Défaut : aujourd’hui.',
        )

    def handle(self, *args, **options):
        raw = (options.get('date') or '').strip()
        day = parse_presence_date(raw) if raw else timezone.localdate()
        closed = close_open_agent_sessions_for_day(day)
        self.stdout.write(self.style.SUCCESS(
            f'[OK] {closed} session(s) agent clôturée(s) pour {day.isoformat()} '
            f'(réf. fin {WORK_END_LABEL}).'
        ))
