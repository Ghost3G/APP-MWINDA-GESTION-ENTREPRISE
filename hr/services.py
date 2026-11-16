from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from .models import LeaveRequest

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

    return {
        'today': today,
        'total_staff': total_staff,
        'on_leave_today': on_leave_today,
        'pending_leaves': pending_leaves,
        'upcoming_leaves': upcoming_leaves,
        'by_department': by_department,
        'recent_pending': recent_pending,
        'leaves_today': leaves_today,
    }


def leave_queryset_for(user, *, can_review):
    qs = LeaveRequest.objects.select_related('user', 'reviewed_by')
    if can_review:
        return qs
    return qs.filter(user=user)
