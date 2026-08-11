"""Présence agents — basée sur les connexions (AuditLog login/logout)."""
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, time, timedelta
from types import SimpleNamespace
import random

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from .models import AuditLog

ILLUSTRATION_PATH = '/presence/illustration/'

# Horaires de service officiels
# Lun–Ven : 08:30 → 17:30 | Samedi : 09:00 → 13:00 | Dimanche : fermé
WEEKDAY_START = time(8, 30)
WEEKDAY_END = time(17, 30)
SATURDAY_START = time(9, 0)
SATURDAY_END = time(13, 0)
WARN_BEFORE = timedelta(minutes=30)

SCHEDULE_SUMMARY_LABEL = 'Lun–Ven 08:30–17:30 · Sam 09:00–13:00'
WEEKDAY_RANGE_LABEL = 'Lundi – Vendredi : 08:30 – 17:30'
SATURDAY_RANGE_LABEL = 'Samedi : 09:00 – 13:00'
SUNDAY_RANGE_LABEL = 'Dimanche : fermé'

# Alias = horaires en semaine (rétrocompat / défauts UI)
WORK_START = WEEKDAY_START
WORK_END = WEEKDAY_END
WORK_WARN = time(17, 0)  # 30 min avant 17:30
WORK_START_HOUR = 8.5
WORK_END_HOUR = 17.5
WORK_START_LABEL = '08:30'
WORK_END_LABEL = '17:30'
WORK_WARN_LABEL = '17:00'


def _time_to_hour_float(value):
    return round(value.hour + value.minute / 60 + value.second / 3600, 2)


def work_schedule_for_day(day=None):
    """
    Horaires du jour (Africa/Kinshasa).
    Lun–Ven 08:30–17:30 · Sam 09:00–13:00 · Dimanche fermé.
    """
    day = day or timezone.localdate()
    weekday = day.weekday()  # 0=lun … 5=sam, 6=dim

    if weekday == 6:
        return SimpleNamespace(
            day=day,
            is_open=False,
            start=None,
            end=None,
            warn=None,
            start_hour=None,
            end_hour=None,
            start_label='—',
            end_label='—',
            warn_label='—',
            day_name='Dimanche',
            range_label=SUNDAY_RANGE_LABEL,
            short_label='Fermé',
        )

    if weekday == 5:
        start, end = SATURDAY_START, SATURDAY_END
        day_name = 'Samedi'
        range_label = SATURDAY_RANGE_LABEL
    else:
        start, end = WEEKDAY_START, WEEKDAY_END
        day_name = (
            'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi'
        )[weekday]
        range_label = WEEKDAY_RANGE_LABEL

    warn_dt = datetime.combine(day, end) - WARN_BEFORE
    warn = warn_dt.time()
    return SimpleNamespace(
        day=day,
        is_open=True,
        start=start,
        end=end,
        warn=warn,
        start_hour=_time_to_hour_float(start),
        end_hour=_time_to_hour_float(end),
        start_label=start.strftime('%H:%M'),
        end_label=end.strftime('%H:%M'),
        warn_label=warn.strftime('%H:%M'),
        day_name=day_name,
        range_label=range_label,
        short_label=f'{start.strftime("%H:%M")} – {end.strftime("%H:%M")}',
    )


def service_hours_banner_payload(day=None):
    """Données pour le bandeau horaires visible dans toute l’app."""
    schedule = work_schedule_for_day(day)
    return {
        'weekday_label': WEEKDAY_RANGE_LABEL,
        'saturday_label': SATURDAY_RANGE_LABEL,
        'sunday_label': SUNDAY_RANGE_LABEL,
        'summary_label': SCHEDULE_SUMMARY_LABEL,
        'today_open': schedule.is_open,
        'today_name': schedule.day_name,
        'today_short': schedule.short_label,
        'today_range': schedule.range_label,
        'today_start': schedule.start_label,
        'today_end': schedule.end_label,
    }

FRENCH_MONTHS = (
    '',
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
)


def french_month_year(day):
    return f'{FRENCH_MONTHS[day.month]} {day.year}'


def _day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = timezone.make_aware(datetime.combine(day, time.max))
    return start, end


def _to_hour_float(dt):
    local = timezone.localtime(dt)
    return round(local.hour + local.minute / 60 + local.second / 3600, 2)


def _first_login_of_day(sessions_for_day):
    if not sessions_for_day:
        return None
    return min(sessions_for_day, key=lambda s: s['login_at'])


def _last_logout_of_day(sessions_for_day):
    closed = [s for s in sessions_for_day if s['logout_at']]
    if not closed:
        return None
    return max(closed, key=lambda s: s['logout_at'])


def month_bounds(year, month):
    last_day = monthrange(year, month)[1]
    start_day = datetime(year, month, 1).date()
    end_day = datetime(year, month, last_day).date()
    start, _ = _day_bounds(start_day)
    _, end = _day_bounds(end_day)
    return start_day, end_day, start, end


def parse_presence_date(raw, fallback=None):
    fallback = fallback or timezone.localdate()
    if not raw:
        return fallback
    try:
        return datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return fallback


def parse_presence_month(raw, fallback_date=None):
    """Retourne (year, month) depuis YYYY-MM ou depuis une date."""
    fallback_date = fallback_date or timezone.localdate()
    if raw:
        try:
            parsed = datetime.strptime(raw, '%Y-%m')
            return parsed.year, parsed.month
        except ValueError:
            pass
    return fallback_date.year, fallback_date.month


def format_duration(seconds):
    if seconds is None:
        return '—'
    seconds = max(int(seconds), 0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'


def build_sessions(*, start, end, user=None):
    """Sessions login→logout sur une plage datetime, optionnellement pour un agent."""
    login_qs = AuditLog.objects.filter(
        action='login_success',
        created_at__gte=start,
        created_at__lte=end,
        user__isnull=False,
    ).select_related('user').order_by('created_at')
    if user is not None:
        login_qs = login_qs.filter(user=user)

    logins = list(login_qs)
    if not logins:
        return []

    user_ids = {entry.user_id for entry in logins}
    logout_qs = AuditLog.objects.filter(
        action='logout',
        user_id__in=user_ids,
        created_at__gte=start,
        created_at__lte=end + timedelta(days=1),
    ).order_by('created_at')
    if user is not None:
        logout_qs = logout_qs.filter(user=user)

    logouts_by_user = defaultdict(list)
    for entry in logout_qs:
        logouts_by_user[entry.user_id].append(entry)

    sessions = []
    for login in logins:
        matched_logout = None
        remaining = []
        for logout in logouts_by_user.get(login.user_id, []):
            if matched_logout is None and logout.created_at >= login.created_at:
                matched_logout = logout
            else:
                remaining.append(logout)
        logouts_by_user[login.user_id] = remaining

        duration_seconds = None
        if matched_logout:
            duration_seconds = int((matched_logout.created_at - login.created_at).total_seconds())

        login_local = timezone.localtime(login.created_at)
        logout_local = timezone.localtime(matched_logout.created_at) if matched_logout else None
        day_schedule = work_schedule_for_day(login_local.date())
        if day_schedule.is_open:
            arrival_status = 'on_time' if login_local.time() <= day_schedule.start else 'late'
            if logout_local:
                departure_status = (
                    'on_time' if logout_local.time() >= day_schedule.end else 'early'
                )
            else:
                departure_status = 'online'
        else:
            arrival_status = 'on_time'
            departure_status = 'online' if not logout_local else 'on_time'

        sessions.append({
            'user': login.user,
            'login_at': login.created_at,
            'logout_at': matched_logout.created_at if matched_logout else None,
            'duration_seconds': duration_seconds,
            'duration_label': format_duration(duration_seconds),
            'is_online': matched_logout is None,
            'arrival_status': arrival_status,
            'departure_status': departure_status,
        })
    sessions.sort(key=lambda row: row['login_at'], reverse=True)
    return sessions


def build_presence_sessions(selected_date):
    """Liste des sessions de connexion pour une journée."""
    local_today = timezone.localdate()
    if selected_date < local_today:
        close_open_sessions_at_midnight_for_day(selected_date)
    # Complète automatiquement les départs agents à la fin de service si la journée est close.
    close_open_agent_sessions_for_day(selected_date)
    start, end = _day_bounds(selected_date)
    return build_sessions(start=start, end=end)


def work_end_datetime(day):
    schedule = work_schedule_for_day(day)
    if not schedule.is_open:
        return None
    return timezone.make_aware(datetime.combine(day, schedule.end))


def work_warn_datetime(day):
    schedule = work_schedule_for_day(day)
    if not schedule.is_open:
        return None
    return timezone.make_aware(datetime.combine(day, schedule.warn))


MIDNIGHT_LOGOUT_LABEL = '00:00'


def midnight_datetime(day):
    """00:00 du lendemain = clôture calendaire de la journée."""
    next_day = day + timedelta(days=1)
    return timezone.make_aware(datetime.combine(next_day, time.min))


def is_presence_auto_close_target(user):
    """Agents uniquement — les directeurs / admin restent connectés après la fin de service."""
    if not user:
        return False
    if getattr(user, 'is_superuser', False):
        return False
    role = (getattr(user, 'role', '') or '').strip().lower()
    return role == 'agent'


def _close_agent_time_entries(user, closed_at):
    try:
        from projects.models import AgentTimeEntry
    except Exception:
        return 0

    closed = 0
    open_entries = AgentTimeEntry.objects.filter(
        user=user,
        entry_type__in=['work', 'pause', 'task'],
        ended_at__isnull=True,
        started_at__lte=closed_at,
    )
    for entry in open_entries:
        elapsed = int((closed_at - entry.started_at).total_seconds())
        entry.duration_seconds = entry.duration_seconds + max(elapsed, 0)
        entry.ended_at = closed_at
        entry.save(update_fields=['duration_seconds', 'ended_at'])
        closed += 1
    return closed


def _workday_login_cutoff(day):
    """Les connexions après la fin de service sont hors journée : on ne les écrase pas."""
    return work_end_datetime(day)


def close_open_session_for_user(user, *, day=None, reason='auto_work_end'):
    """
    Complète la présence : ajoute un départ à la fin de service pour chaque connexion
    de la journée de travail encore ouverte.

    Ne supprime jamais les login/logout existants (arrivées et départs réels conservés).
    Ne touche pas aux connexions démarrées après la fin de service (soir / consultation).
    """
    if not is_presence_auto_close_target(user):
        return False

    local_now = timezone.localtime()
    day = day or local_now.date()
    schedule = work_schedule_for_day(day)
    if not schedule.is_open:
        return False

    closed_at = work_end_datetime(day)
    start, end = _day_bounds(day)

    # Ne ferme que si la fin de journée est déjà passée (ou journée antérieure).
    if day > local_now.date():
        return False
    if day == local_now.date() and local_now.time() < schedule.end:
        return False

    # Uniquement les connexions de la plage 00:00 → fin de service (journée de travail).
    workday_logins = list(
        AuditLog.objects.filter(
            user=user,
            action='login_success',
            created_at__gte=start,
            created_at__lte=closed_at,
        ).order_by('created_at')
    )
    if not workday_logins:
        _close_agent_time_entries(user, closed_at)
        return False

    logouts = list(
        AuditLog.objects.filter(
            user=user,
            action='logout',
            created_at__gte=start,
            created_at__lte=end + timedelta(hours=12),
        ).order_by('created_at')
    )

    # Appariement FIFO identique à build_sessions — on n'ajoute un départ
    # qu'aux connexions encore sans logout, sans toucher aux autres.
    remaining_logouts = list(logouts)
    closed_any = False
    extra_seconds = 0
    for login in workday_logins:
        matched = None
        kept = []
        for logout in remaining_logouts:
            if matched is None and logout.created_at >= login.created_at:
                matched = logout
            else:
                kept.append(logout)
        remaining_logouts = kept
        if matched is not None:
            continue

        logout_at = max(closed_at, login.created_at + timedelta(minutes=1))
        if extra_seconds:
            logout_at = logout_at + timedelta(seconds=extra_seconds)
        extra_seconds += 1
        AuditLog.objects.create(
            user=user,
            action='logout',
            path='/system/auto-presence-close/',
            method='SYSTEM',
            metadata={
                'reason': reason,
                'work_end': schedule.end_label,
                'preserves_login_at': login.created_at.isoformat(),
            },
            created_at=logout_at,
        )
        closed_any = True

    _close_agent_time_entries(user, closed_at)
    return closed_any


def close_open_agent_sessions_for_day(day=None):
    """Ferme toutes les sessions agents ouvertes pour une journée (sauf directeurs)."""
    User = get_user_model()
    local_now = timezone.localtime()
    day = day or local_now.date()
    schedule = work_schedule_for_day(day)

    if day > local_now.date():
        return 0
    if not schedule.is_open:
        return 0
    if day == local_now.date() and local_now.time() < schedule.end:
        return 0

    start, end = _day_bounds(day)
    cutoff = _workday_login_cutoff(day)
    if cutoff is None:
        return 0
    agent_ids = (
        AuditLog.objects.filter(
            action='login_success',
            created_at__gte=start,
            created_at__lte=cutoff,
            user__isnull=False,
            user__role='agent',
            user__is_superuser=False,
        )
        .values_list('user_id', flat=True)
        .distinct()
    )
    closed = 0
    for user in User.objects.filter(id__in=agent_ids, is_active=True):
        if close_open_session_for_user(user, day=day):
            closed += 1
    return closed


def close_open_session_for_user_at_midnight(user, *, day=None, reason='auto_midnight'):
    """
    Clôture à minuit toutes les connexions encore ouvertes sur une journée calendaire.
    S'applique à tous les rôles (agents, directeurs, admin).
    """
    if not user:
        return False

    local_now = timezone.localtime()
    day = day or (local_now.date() - timedelta(days=1))
    if day >= local_now.date():
        return False

    closed_at = midnight_datetime(day)
    start, end = _day_bounds(day)

    day_logins = list(
        AuditLog.objects.filter(
            user=user,
            action='login_success',
            created_at__gte=start,
            created_at__lte=end,
        ).order_by('created_at')
    )
    if not day_logins:
        return False

    logouts = list(
        AuditLog.objects.filter(
            user=user,
            action='logout',
            created_at__gte=start,
            created_at__lte=closed_at + timedelta(hours=1),
        ).order_by('created_at')
    )

    remaining_logouts = list(logouts)
    closed_any = False
    extra_seconds = 0
    for login in day_logins:
        matched = None
        kept = []
        for logout in remaining_logouts:
            if matched is None and logout.created_at >= login.created_at:
                matched = logout
            else:
                kept.append(logout)
        remaining_logouts = kept
        if matched is not None:
            continue

        logout_at = max(closed_at, login.created_at + timedelta(minutes=1))
        if extra_seconds:
            logout_at = logout_at + timedelta(seconds=extra_seconds)
        extra_seconds += 1
        AuditLog.objects.create(
            user=user,
            action='logout',
            path='/system/auto-midnight-close/',
            method='SYSTEM',
            metadata={
                'reason': reason,
                'midnight': MIDNIGHT_LOGOUT_LABEL,
                'calendar_day': day.isoformat(),
                'preserves_login_at': login.created_at.isoformat(),
            },
            created_at=logout_at,
        )
        closed_any = True

    if is_presence_auto_close_target(user):
        _close_agent_time_entries(user, closed_at)
    return closed_any


def close_open_sessions_at_midnight_for_day(day=None):
    """Ferme à minuit les sessions ouvertes pour une journée (tous les utilisateurs actifs)."""
    User = get_user_model()
    local_now = timezone.localtime()
    day = day or (local_now.date() - timedelta(days=1))
    if day >= local_now.date():
        return 0

    start, end = _day_bounds(day)
    user_ids = (
        AuditLog.objects.filter(
            action='login_success',
            created_at__gte=start,
            created_at__lte=end,
            user__isnull=False,
            user__is_active=True,
        )
        .values_list('user_id', flat=True)
        .distinct()
    )
    closed = 0
    for user in User.objects.filter(id__in=user_ids, is_active=True):
        if close_open_session_for_user_at_midnight(user, day=day):
            closed += 1
    return closed


def flush_all_django_sessions():
    """Invalide toutes les sessions Django encore actives."""
    try:
        from django.contrib.sessions.models import Session
    except Exception:
        return 0
    qs = Session.objects.filter(expire_date__gte=timezone.now())
    count = qs.count()
    qs.delete()
    return count


def invalidate_django_sessions_for_users(user_ids):
    """Supprime les sessions Django des utilisateurs indiqués."""
    if not user_ids:
        return 0
    try:
        from django.contrib.sessions.models import Session
    except Exception:
        return 0

    target_ids = {str(uid) for uid in user_ids}
    removed = 0
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            uid = session.get_decoded().get('_auth_user_id')
        except Exception:
            continue
        if uid in target_ids:
            session.delete()
            removed += 1
    return removed


def run_midnight_logout_cycle(*, day=None):
    """
    Cycle minuit : clôture présence de la veille + invalidation de toutes les sessions Django.
    """
    local_now = timezone.localtime()
    day = day or (local_now.date() - timedelta(days=1))
    presence_closed = close_open_sessions_at_midnight_for_day(day)
    sessions_flushed = flush_all_django_sessions()
    return {
        'day': day.isoformat(),
        'presence_closed': presence_closed,
        'sessions_flushed': sessions_flushed,
    }


def should_force_midnight_logout_now(user):
    """
    True si l'utilisateur est encore connecté alors que sa dernière connexion
    date d'un jour calendaire précédent (nouvelle journée à minuit).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    local_now = timezone.localtime()
    today_start = timezone.make_aware(datetime.combine(local_now.date(), time.min))
    last_login = (
        AuditLog.objects.filter(user=user, action='login_success')
        .order_by('-created_at')
        .first()
    )
    if not last_login:
        return True
    return last_login.created_at < today_start


def agent_still_in_workday_session(user, day=None):
    """
    True si la dernière connexion du jour a commencé avant la fin de service
    (session de travail à clôturer / déconnecter).
    False si pas de connexion, jour fermé, ou reconnexion après la fin de service.
    """
    if not is_presence_auto_close_target(user):
        return False
    local_now = timezone.localtime()
    day = day or local_now.date()
    schedule = work_schedule_for_day(day)
    if not schedule.is_open:
        return False
    start, end = _day_bounds(day)
    last_login = (
        AuditLog.objects.filter(
            user=user,
            action='login_success',
            created_at__gte=start,
            created_at__lte=end,
        )
        .order_by('-created_at')
        .first()
    )
    if not last_login:
        return False
    return timezone.localtime(last_login.created_at).time() < schedule.end


def should_force_agent_logout_now(user):
    """Déconnecte seulement une session de travail encore active après la fin de service."""
    if not is_presence_auto_close_target(user):
        return False
    schedule = work_schedule_for_day()
    if not schedule.is_open:
        return False
    if timezone.localtime().time() < schedule.end:
        return False
    return agent_still_in_workday_session(user)


def agent_logout_warning_payload(user=None):
    """
    Données pour l'alerte UI : visible 30 min avant la fin de service du jour.
    Lun–Ven → alerte 17:00 / fin 17:30 · Samedi → alerte 12:30 / fin 13:00.
    """
    local_now = timezone.localtime()
    day = local_now.date()
    schedule = work_schedule_for_day(day)

    if (
        not schedule.is_open
        or (user is not None and not is_presence_auto_close_target(user))
    ):
        return {
            'enabled': False,
            'active': False,
            'warn_label': schedule.warn_label if schedule.is_open else WORK_WARN_LABEL,
            'logout_label': schedule.end_label if schedule.is_open else WORK_END_LABEL,
            'seconds_remaining': 0,
            'server_now_iso': local_now.isoformat(),
            'logout_at_iso': '',
            'warn_at_iso': '',
        }

    warn_at = work_warn_datetime(day)
    logout_at = work_end_datetime(day)
    seconds_remaining = max(0, int((logout_at - local_now).total_seconds()))
    active = local_now >= warn_at and local_now < logout_at and (
        user is None or agent_still_in_workday_session(user, day=day)
    )
    return {
        'enabled': True,
        'active': active,
        'warn_label': schedule.warn_label,
        'logout_label': schedule.end_label,
        'seconds_remaining': seconds_remaining,
        'server_now_iso': local_now.isoformat(),
        'logout_at_iso': logout_at.isoformat(),
        'warn_at_iso': warn_at.isoformat(),
    }


def build_agent_monthly_sessions(agent, year, month):
    """Liste de présence mensuelle d'un agent + totaux + rythme (diagrammes)."""
    start_day, end_day, start, end = month_bounds(year, month)
    cursor = start_day
    today = timezone.localdate()
    while cursor <= end_day and cursor <= today:
        close_open_agent_sessions_for_day(cursor)
        cursor += timedelta(days=1)
    sessions = build_sessions(start=start, end=end, user=agent)
    total_seconds = sum(s['duration_seconds'] or 0 for s in sessions)
    present_days = {
        timezone.localtime(s['login_at']).date()
        for s in sessions
    }
    days = (end_day - start_day).days + 1
    rhythm = build_agent_rhythm_charts(agent, end_day, days=days)
    return {
        'agent': agent,
        'year': year,
        'month': month,
        'start_day': start_day,
        'end_day': end_day,
        'month_label': french_month_year(start_day),
        'period_label': french_month_year(start_day),
        'sessions': sessions,
        'session_count': len(sessions),
        'present_days': len(present_days),
        'total_seconds': total_seconds,
        'total_duration_label': format_duration(total_seconds),
        'work_start': WORK_START_LABEL,
        'work_end': WORK_END_LABEL,
        'schedule_summary': SCHEDULE_SUMMARY_LABEL,
        'rhythm_data': rhythm,
    }


def build_agent_login_chart(agent, end_date, days=14):
    """Graphique : nombre de connexions par jour pour un agent."""
    start_date = end_date - timedelta(days=days - 1)
    start, _ = _day_bounds(start_date)
    _, end = _day_bounds(end_date)

    counts = defaultdict(int)
    for created_at in AuditLog.objects.filter(
        user=agent,
        action='login_success',
        created_at__gte=start,
        created_at__lte=end,
    ).values_list('created_at', flat=True):
        local_day = timezone.localtime(created_at).date()
        counts[local_day] += 1

    labels = []
    values = []
    cursor = start_date
    while cursor <= end_date:
        labels.append(cursor.strftime('%d/%m'))
        values.append(counts.get(cursor, 0))
        cursor += timedelta(days=1)

    return {
        'labels': labels,
        'counts': values,
        'total': sum(values),
    }


def build_agent_rhythm_charts(agent, end_date, days=14):
    """
    Diagrammes rythme de travail d'un agent :
    arrivées, départs, absences sur les jours ouvrés (Lun–Sam).
    """
    start_date = end_date - timedelta(days=days - 1)
    start, _ = _day_bounds(start_date)
    _, end = _day_bounds(end_date)
    sessions = build_sessions(start=start, end=end, user=agent)
    end_schedule = work_schedule_for_day(end_date)

    by_day = defaultdict(list)
    for session in sessions:
        day = timezone.localtime(session['login_at']).date()
        by_day[day].append(session)

    labels = []
    arrival_hours = []
    departure_hours = []
    arrival_ref = []
    departure_ref = []
    presence_flags = []

    present_days = 0
    absent_days = 0
    late_arrivals = 0
    early_departures = 0
    on_time_arrivals = 0
    on_time_departures = 0

    cursor = start_date
    while cursor <= end_date:
        day_schedule = work_schedule_for_day(cursor)
        if day_schedule.is_open:
            labels.append(cursor.strftime('%d/%m'))
            arrival_ref.append(day_schedule.start_hour)
            departure_ref.append(day_schedule.end_hour)
            day_sessions = by_day.get(cursor, [])
            first = _first_login_of_day(day_sessions)
            last = _last_logout_of_day(day_sessions)

            if first:
                present_days += 1
                presence_flags.append(1)
                arr_h = _to_hour_float(first['login_at'])
                arrival_hours.append(arr_h)
                if arr_h <= day_schedule.start_hour:
                    on_time_arrivals += 1
                else:
                    late_arrivals += 1
            else:
                absent_days += 1
                presence_flags.append(0)
                arrival_hours.append(None)

            if last:
                dep_h = _to_hour_float(last['logout_at'])
                departure_hours.append(dep_h)
                if dep_h >= day_schedule.end_hour:
                    on_time_departures += 1
                else:
                    early_departures += 1
            else:
                departure_hours.append(None)
        cursor += timedelta(days=1)

    return {
        'labels': labels,
        'arrival_hours': arrival_hours,
        'departure_hours': departure_hours,
        'arrival_ref': arrival_ref,
        'departure_ref': departure_ref,
        'presence_flags': presence_flags,
        'work_start': end_schedule.start_hour if end_schedule.is_open else WORK_START_HOUR,
        'work_end': end_schedule.end_hour if end_schedule.is_open else WORK_END_HOUR,
        'work_start_label': (
            end_schedule.start_label if end_schedule.is_open else WORK_START_LABEL
        ),
        'work_end_label': (
            end_schedule.end_label if end_schedule.is_open else WORK_END_LABEL
        ),
        'schedule_summary': SCHEDULE_SUMMARY_LABEL,
        'stats': {
            'present_days': present_days,
            'absent_days': absent_days,
            'late_arrivals': late_arrivals,
            'early_departures': early_departures,
            'on_time_arrivals': on_time_arrivals,
            'on_time_departures': on_time_departures,
        },
        'absence_chart': {
            'labels': ['Présents', 'Absents'],
            'values': [present_days, absent_days],
        },
    }


def build_day_team_rhythm(selected_date, agents):
    """Répartition équipe du jour : arrivées / départs / absences."""
    schedule = work_schedule_for_day(selected_date)
    sessions = build_presence_sessions(selected_date)
    by_user = defaultdict(list)
    for session in sessions:
        by_user[session['user'].id].append(session)

    start_h = schedule.start_hour if schedule.is_open else WORK_START_HOUR
    end_h = schedule.end_hour if schedule.is_open else WORK_END_HOUR
    start_label = schedule.start_label if schedule.is_open else WORK_START_LABEL
    end_label = schedule.end_label if schedule.is_open else WORK_END_LABEL

    on_time = late = early_leave = left_on_time = still_online = absent = 0
    for agent in agents:
        day_sessions = by_user.get(agent.id, [])
        if not day_sessions:
            absent += 1
            continue
        first = _first_login_of_day(day_sessions)
        last = _last_logout_of_day(day_sessions)
        if first and _to_hour_float(first['login_at']) <= start_h:
            on_time += 1
        else:
            late += 1
        if not last:
            still_online += 1
        elif _to_hour_float(last['logout_at']) >= end_h:
            left_on_time += 1
        else:
            early_leave += 1

    return {
        'arrival': {
            'labels': [f'À l’heure (≤ {start_label})', 'En retard', 'Absents'],
            'values': [on_time, late, absent],
        },
        'departure': {
            'labels': [f'Parti ≥ {end_label}', 'Parti tôt', 'Encore connectés', 'Absents'],
            'values': [left_on_time, early_leave, still_online, absent],
        },
        'counts': {
            'on_time': on_time,
            'late': late,
            'early_leave': early_leave,
            'left_on_time': left_on_time,
            'still_online': still_online,
            'absent': absent,
        },
    }


def build_agent_presence_summary(selected_date, agents):
    """Résumé par agent pour la journée : nb connexions + dernière connexion."""
    start, end = _day_bounds(selected_date)
    login_rows = (
        AuditLog.objects.filter(
            action='login_success',
            created_at__gte=start,
            created_at__lte=end,
            user__isnull=False,
        )
        .values('user_id')
        .annotate(login_count=Count('id'))
    )
    counts = {row['user_id']: row['login_count'] for row in login_rows}

    last_logins = {}
    for entry in (
        AuditLog.objects.filter(
            action='login_success',
            created_at__gte=start,
            created_at__lte=end,
            user__isnull=False,
        )
        .order_by('-created_at')
    ):
        if entry.user_id not in last_logins:
            last_logins[entry.user_id] = entry.created_at

    first_logins = {}
    last_logouts = {}
    day_sessions = build_presence_sessions(selected_date)
    by_user = defaultdict(list)
    for session in day_sessions:
        by_user[session['user'].id].append(session)
    for user_id, rows in by_user.items():
        first = _first_login_of_day(rows)
        last = _last_logout_of_day(rows)
        if first:
            first_logins[user_id] = first['login_at']
        if last:
            last_logouts[user_id] = last['logout_at']

    day_schedule = work_schedule_for_day(selected_date)
    summary = []
    for agent in agents:
        first_at = first_logins.get(agent.id)
        last_at = last_logouts.get(agent.id)
        arrival_status = None
        departure_status = None
        if first_at and day_schedule.is_open:
            arrival_status = (
                'on_time'
                if timezone.localtime(first_at).time() <= day_schedule.start
                else 'late'
            )
        elif first_at:
            arrival_status = 'on_time'
        if last_at and day_schedule.is_open:
            departure_status = (
                'on_time'
                if timezone.localtime(last_at).time() >= day_schedule.end
                else 'early'
            )
        elif last_at:
            departure_status = 'on_time'
        elif counts.get(agent.id, 0) > 0:
            departure_status = 'online'

        summary.append({
            'user': agent,
            'login_count': counts.get(agent.id, 0),
            'last_login_at': last_logins.get(agent.id) or agent.last_login,
            'first_login_at': first_at,
            'last_logout_at': last_at,
            'present_today': counts.get(agent.id, 0) > 0,
            'arrival_status': arrival_status,
            'departure_status': departure_status,
        })
    summary.sort(key=lambda row: (-row['login_count'], row['user'].get_display_name().lower()))
    return summary


def seed_presence_illustration(days=14):
    """
    Heures d'illustration selon l’horaire du jour (Lun–Ven / Samedi).
    Remplace uniquement les logs marqués illustration (ré-exécutable).
    """
    User = get_user_model()
    AuditLog.objects.filter(path=ILLUSTRATION_PATH).delete()

    agents = list(
        User.objects.filter(is_active=True)
        .exclude(role='admin')
        .order_by('id')
    )
    if not agents:
        agents = list(User.objects.filter(is_active=True).order_by('id')[:8])

    today = timezone.localdate()
    created = 0
    rng = random.Random(20260730)

    for offset in range(days):
        day = today - timedelta(days=offset)
        schedule = work_schedule_for_day(day)
        if not schedule.is_open:
            continue

        for index, agent in enumerate(agents):
            if rng.random() < 0.15:
                continue

            arrive_offset_min = rng.randint(-20, 45)
            login_at = timezone.make_aware(
                datetime.combine(day, schedule.start) + timedelta(minutes=arrive_offset_min)
            )

            leave_offset_min = rng.randint(-40, 40)
            logout_at = timezone.make_aware(
                datetime.combine(day, schedule.end) + timedelta(minutes=leave_offset_min)
            )
            if logout_at <= login_at:
                logout_at = login_at + timedelta(hours=4)

            meta = {
                'illustration': True,
                'agent_id': agent.id,
                'work_hours': f'{schedule.start_label}-{schedule.end_label}',
            }
            AuditLog.objects.create(
                user=agent,
                action='login_success',
                path=ILLUSTRATION_PATH,
                method='POST',
                metadata=meta,
                created_at=login_at,
            )
            AuditLog.objects.create(
                user=agent,
                action='logout',
                path=ILLUSTRATION_PATH,
                method='POST',
                metadata=meta,
                created_at=logout_at,
            )
            created += 2

    return {
        'agents': len(agents),
        'logs': created,
        'work_start': WORK_START_LABEL,
        'work_end': WORK_END_LABEL,
        'schedule': SCHEDULE_SUMMARY_LABEL,
    }
