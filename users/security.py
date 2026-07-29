from datetime import timedelta

from django.utils import timezone

from .models import AuditLog, LoginAttempt

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def record_login_attempt(username, ip_address, success):
    LoginAttempt.objects.create(
        username=username,
        ip_address=ip_address,
        success=success,
    )


def is_login_locked(username, ip_address):
    window_start = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
    attempts = LoginAttempt.objects.filter(
        username=username,
        ip_address=ip_address,
        success=False,
        attempted_at__gte=window_start,
    ).count()
    return attempts >= MAX_FAILED_ATTEMPTS


def clear_failed_attempts(username, ip_address):
    LoginAttempt.objects.filter(
        username=username,
        ip_address=ip_address,
        success=False,
    ).delete()


def write_audit_log(user, action, path="", method="", metadata=None):
    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        path=path[:300],
        method=method[:10],
        metadata=metadata or {},
    )
