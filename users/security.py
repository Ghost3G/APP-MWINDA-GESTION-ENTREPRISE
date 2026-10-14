from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone

from .models import AuditLog, LoginAttempt

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def get_client_ip(request):
    """IP client pour audit/lockout.

    Derrière un reverse-proxy (Render), on lit X-Forwarded-For
    mais on prend la dernière IP non vide (plus fiable que la première spoofable).
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        parts = [p.strip() for p in forwarded.split(',') if p.strip()]
        if parts:
            return parts[-1]
    return request.META.get('REMOTE_ADDR') or ''


def authenticate_login(request, raw_username, password):
    """Accepte l'identifiant, ou le nom, sans tenir compte des majuscules ni des espaces."""
    raw = " ".join((raw_username or "").split())
    if not raw or not password:
        return None

    User = get_user_model()
    candidates = []

    def add(value):
        value = (value or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    folded = raw.casefold()
    add(raw)
    add(folded)
    add(folded.replace(" ", "."))

    lookup = folded.replace(" ", ".")
    match = User.objects.filter(username__iexact=lookup).only("id", "username").first()
    if match is None and " " in raw:
        first, _, last = raw.partition(" ")
        match = (
            User.objects.filter(first_name__iexact=first, last_name__iexact=last)
            .only("id", "username")
            .order_by("id")
            .first()
        )
    if match is not None:
        add(match.username)

    for candidate in candidates:
        user = authenticate(request, username=candidate, password=password)
        if user is not None:
            return user
    return None


def record_login_attempt(username, ip_address, success):
    LoginAttempt.objects.create(
        username=username,
        ip_address=ip_address,
        success=success,
    )


def is_login_locked(username, ip_address):
    """Blocage anti-bruteforce : par identifiant (prioritaire) et par IP."""
    window_start = timezone.now() - timedelta(minutes=LOCKOUT_MINUTES)
    failed_by_user = LoginAttempt.objects.filter(
        username=username,
        success=False,
        attempted_at__gte=window_start,
    ).count()
    if failed_by_user >= MAX_FAILED_ATTEMPTS:
        return True

    # Seuil plus haut sur l'IP pour limiter les floods multi-comptes
    failed_by_ip = LoginAttempt.objects.filter(
        ip_address=ip_address,
        success=False,
        attempted_at__gte=window_start,
    ).count()
    return failed_by_ip >= (MAX_FAILED_ATTEMPTS * 3)


def clear_failed_attempts(username, ip_address):
    # On nettoie tout l'historique d'échec du compte (pas seulement l'IP)
    LoginAttempt.objects.filter(
        username=username,
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
