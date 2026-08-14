"""Heures supplémentaires — calcul et synthèse par jours."""
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import OvertimeDayEntry
from .presence import (
    _day_bounds,
    build_sessions,
    french_month_year,
    work_schedule_for_day,
)

OVERTIME_HOURS_PER_DAY = Decimal('8')
MIN_OVERTIME_MINUTES = 30


def parse_overtime_period(period_key, anchor=None):
    """Retourne (start_date, end_date, label) pour semaine / mois / année."""
    anchor = anchor or timezone.localdate()
    period_key = (period_key or 'month').strip().lower()
    if period_key == 'week':
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
        label = f'Semaine du {start.strftime("%d/%m/%Y")} au {end.strftime("%d/%m/%Y")}'
    elif period_key == 'year':
        start = anchor.replace(month=1, day=1)
        end = anchor.replace(month=12, day=31)
        label = f'Année {anchor.year}'
    else:
        period_key = 'month'
        start = anchor.replace(day=1)
        end = anchor.replace(day=monthrange(anchor.year, anchor.month)[1])
        label = french_month_year(start)
    return period_key, start, end, label


def _quantize_days(value):
    return value.quantize(Decimal('0.25'), rounding=ROUND_HALF_UP)


def _hours_to_days(hours):
    if hours <= 0:
        return Decimal('0')
    return _quantize_days(Decimal(str(hours)) / OVERTIME_HOURS_PER_DAY)


def _overlap_seconds(start_a, end_a, start_b, end_b):
    start = max(start_a, start_b)
    end = min(end_a, end_b)
    if end <= start:
        return 0
    return int((end - start).total_seconds())


def _outside_service_seconds(login_at, logout_at, day):
    """Secondes de session en dehors des horaires officiels du jour."""
    if not logout_at or logout_at <= login_at:
        return 0

    schedule = work_schedule_for_day(day)
    start_day, end_day = _day_bounds(day)

    if not schedule.is_open:
        # Dimanche : toute la session sur ce jour compte en sup
        day_start = max(login_at, start_day)
        day_end = min(logout_at, end_day)
        return max(0, int((day_end - day_start).total_seconds()))

    service_start = timezone.make_aware(datetime.combine(day, schedule.start))
    service_end = timezone.make_aware(datetime.combine(day, schedule.end))

    total = 0
    # Avant ouverture
    if login_at < service_start:
        seg_end = min(logout_at, service_start)
        total += max(0, int((seg_end - login_at).total_seconds()))
    # Après fermeture (ex. samedi après 13:00)
    if logout_at > service_end:
        seg_start = max(login_at, service_end)
        total += max(0, int((logout_at - seg_start).total_seconds()))
    return total


def _session_overtime_by_day(session):
    """Répartit le hors-horaire d'une session par jour calendaire."""
    login_at = session['login_at']
    logout_at = session.get('logout_at')
    if not logout_at:
        return {}

    per_day = defaultdict(int)
    cursor = timezone.localtime(login_at).date()
    end_date = timezone.localtime(logout_at).date()
    while cursor <= end_date:
        day_start, day_end = _day_bounds(cursor)
        seg_start = max(login_at, day_start)
        seg_end = min(logout_at, day_end)
        if seg_end > seg_start:
            seconds = _outside_service_seconds(seg_start, seg_end, cursor)
            if seconds >= MIN_OVERTIME_MINUTES * 60:
                per_day[cursor] += seconds
        cursor += timedelta(days=1)
    return dict(per_day)


def build_overtime_suggestions(users, start, end):
    """
    Suggestions depuis les connexions (non comptées tant que le DT ne valide pas).
    Ignore les sessions encore ouvertes.
    """
    start_dt, _ = _day_bounds(start)
    _, end_dt = _day_bounds(end)
    sessions = build_sessions(start=start_dt, end=end_dt)
    user_ids = {u.id for u in users}
    existing = {
        (row.user_id, row.work_date)
        for row in OvertimeDayEntry.objects.filter(
            user_id__in=user_ids,
            work_date__gte=start,
            work_date__lte=end,
        )
    }

    suggestions = []
    accumulated = defaultdict(lambda: defaultdict(int))

    for session in sessions:
        user = session.get('user')
        if not user or user.id not in user_ids:
            continue
        if session.get('is_online'):
            continue
        for day, seconds in _session_overtime_by_day(session).items():
            if day < start or day > end:
                continue
            accumulated[user.id][day] += seconds

    User = get_user_model()
    users_by_id = {u.id: u for u in User.objects.filter(id__in=user_ids)}

    for user_id, days_map in accumulated.items():
        user = users_by_id.get(user_id)
        if not user:
            continue
        for day, seconds in sorted(days_map.items()):
            if (user_id, day) in existing:
                continue
            hours = seconds / 3600
            suggested_days = _hours_to_days(hours)
            if suggested_days <= 0:
                continue
            suggestions.append({
                'user': user,
                'work_date': day,
                'hours': round(hours, 2),
                'suggested_days': suggested_days,
            })
    suggestions.sort(key=lambda row: (row['work_date'], row['user'].get_labeled_name()), reverse=True)
    return suggestions


def build_overtime_summary(users, start, end):
    """Totaux et lignes enregistrées par agent."""
    entries = list(
        OvertimeDayEntry.objects.filter(
            user__in=users,
            work_date__gte=start,
            work_date__lte=end,
        )
        .select_related('user', 'created_by')
        .order_by('-work_date', 'user__first_name')
    )
    rows = []
    totals_by_user = defaultdict(lambda: Decimal('0'))
    entries_by_user = defaultdict(list)
    for entry in entries:
        totals_by_user[entry.user_id] += entry.days
        entries_by_user[entry.user_id].append(entry)

    for user in users:
        total = _quantize_days(totals_by_user.get(user.id, Decimal('0')))
        rows.append({
            'user': user,
            'total_days': total,
            'entries': entries_by_user.get(user.id, []),
        })
    rows.sort(key=lambda row: (-row['total_days'], row['user'].get_labeled_name()))
    grand_total = sum((row['total_days'] for row in rows), Decimal('0'))
    return rows, _quantize_days(grand_total)


def format_days_label(days):
    value = _quantize_days(Decimal(days))
    if value == value.to_integral_value():
        label = str(int(value))
    else:
        label = str(value).replace('.', ',')
    return f'{label} j'
