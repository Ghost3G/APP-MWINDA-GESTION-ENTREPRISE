from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from .models import DisciplinaryAction, JobApplication, LeaveRequest, PerformanceReview, TrainingRecord

User = get_user_model()


def build_hr_dashboard_stats():
    today = timezone.localdate()
    active_users = User.objects.filter(is_active=True)
    total_staff = active_users.count()

    on_leave_today = (
        LeaveRequest.objects.filter(
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        )
        .values('user_id')
        .distinct()
        .count()
    )
    pending_leaves = LeaveRequest.objects.filter(status=LeaveRequest.STATUS_PENDING).count()
    upcoming_leaves = LeaveRequest.objects.filter(
        status=LeaveRequest.STATUS_APPROVED,
        start_date__gt=today,
        start_date__lte=today + timedelta(days=14),
    ).count()

    by_department = list(
        active_users.values('org_group')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    recent_pending = list(
        LeaveRequest.objects.filter(status=LeaveRequest.STATUS_PENDING)
        .select_related('user')
        .order_by('start_date', 'id')[:8]
    )
    leaves_today = list(
        LeaveRequest.objects.filter(
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=today,
            end_date__gte=today,
        ).select_related('user').order_by('user__first_name', 'user__username')[:12]
    )

    open_applications = JobApplication.objects.exclude(
        status__in=[JobApplication.STATUS_HIRED, JobApplication.STATUS_REJECTED]
    ).count()
    trainings_active = TrainingRecord.objects.filter(
        status__in=[TrainingRecord.STATUS_PLANNED, TrainingRecord.STATUS_ONGOING]
    ).count()
    reviews_recent = PerformanceReview.objects.filter(
        review_date__gte=today - timedelta(days=90)
    ).count()
    sanctions_recent = DisciplinaryAction.objects.filter(
        action_date__gte=today - timedelta(days=90)
    ).count()

    return {
        'today': today,
        'total_staff': total_staff,
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
        'upcoming_leaves': upcoming_leaves,
        'by_department': by_department,
        'recent_pending': recent_pending,
        'leaves_today': leaves_today,
        'open_applications': open_applications,
        'trainings_active': trainings_active,
        'reviews_recent': reviews_recent,
        'sanctions_recent': sanctions_recent,
    }


def leave_queryset_for(user, *, can_review):
    qs = LeaveRequest.objects.select_related('user', 'reviewed_by')
    if can_review:
        return qs
    return qs.filter(user=user)


def leave_balance_for(user, year=None):
    """Solde congés annuels : quota − jours approuvés/en attente sur l’année."""
    today = timezone.localdate()
    year = year or today.year
    allowance = int(getattr(user, 'annual_leave_days', 18) or 18)
    year_start = today.replace(year=year, month=1, day=1)
    year_end = today.replace(year=year, month=12, day=31)
    used = 0
    pending = 0
    qs = LeaveRequest.objects.filter(
        user=user,
        leave_type=LeaveRequest.TYPE_ANNUAL,
        start_date__lte=year_end,
        end_date__gte=year_start,
        status__in=[LeaveRequest.STATUS_APPROVED, LeaveRequest.STATUS_PENDING],
    )
    for leave in qs:
        # Compte les jours de l’année civile uniquement
        start = max(leave.start_date, year_start)
        end = min(leave.end_date, year_end)
        days = max((end - start).days + 1, 0)
        if leave.status == LeaveRequest.STATUS_APPROVED:
            used += days
        else:
            pending += days
    remaining = max(allowance - used - pending, 0)
    return {
        'year': year,
        'allowance': allowance,
        'used': used,
        'pending': pending,
        'remaining': remaining,
    }
