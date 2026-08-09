"""
Clôture automatique des sessions agents à la fin de service (présence).

Lun–Ven : 17:30 · Samedi : 13:00

Usage :
  python manage.py close_agent_presence
  python manage.py close_agent_presence --date 2026-08-04
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.presence import (
    SCHEDULE_SUMMARY_LABEL,
    close_open_agent_sessions_for_day,
    parse_presence_date,
    work_schedule_for_day,
)


class Command(BaseCommand):
    help = (
        'Ferme les sessions agents ouvertes à la fin de service '
        f'({SCHEDULE_SUMMARY_LABEL}). Directeurs exclus.'
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
        schedule = work_schedule_for_day(day)
        closed = close_open_agent_sessions_for_day(day)
        end_label = schedule.end_label if schedule.is_open else 'fermé'
        self.stdout.write(self.style.SUCCESS(
            f'[OK] {closed} session(s) agent clôturée(s) pour {day.isoformat()} '
            f'(réf. fin {end_label} · {SCHEDULE_SUMMARY_LABEL}).'
        ))
