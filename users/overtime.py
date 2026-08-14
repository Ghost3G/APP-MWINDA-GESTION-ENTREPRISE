"""Heures supplémentaires — synthèse par jours (saisie manuelle)."""
from calendar import monthrange
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import OvertimeDayEntry
from .presence import french_month_year


def parse_overtime_period(period_key, anchor=None):
    """Retourne (period_key, start_date, end_date, label) pour semaine / mois / année."""
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
