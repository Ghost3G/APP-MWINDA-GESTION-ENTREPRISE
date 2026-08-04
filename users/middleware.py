from .security import write_audit_log

# Endpoints à haute fréquence : on évite le bruit dans l'audit générique
_SKIP_AUDIT_PREFIXES = (
    '/static/',
    '/media/',
    '/projects/api/timer/',
    '/api/notifications/',
    '/messaging/api/csrf/',
)

_SKIP_FORCE_LOGOUT_PREFIXES = (
    '/static/',
    '/media/',
    '/login/',
    '/logout/',
)


class AuditLogMiddleware:
    """Simple audit trail for authenticated write actions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.user.is_authenticated:
            path = request.path or ""
            if any(path.startswith(prefix) for prefix in _SKIP_AUDIT_PREFIXES):
                return response
            write_audit_log(
                user=request.user,
                action=f"http_{request.method.lower()}",
                path=path,
                method=request.method,
                metadata={"status_code": response.status_code},
            )
        return response


class AgentWorkEndLogoutMiddleware:
    """
    À partir de 17h30 (Africa/Kinshasa) : déconnecte les agents,
    complète leur présence, laisse les directeurs connectés.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        user = getattr(request, 'user', None)
        if (
            user is not None
            and getattr(user, 'is_authenticated', False)
            and not any(path.startswith(prefix) for prefix in _SKIP_FORCE_LOGOUT_PREFIXES)
        ):
            from django.contrib import messages
            from django.contrib.auth import logout
            from django.shortcuts import redirect
            from django.utils import timezone

            from .presence import (
                WORK_END_LABEL,
                close_open_session_for_user,
                should_force_agent_logout_now,
            )

            if should_force_agent_logout_now(user):
                close_open_session_for_user(user, day=timezone.localdate())
                logout(request)
                messages.info(
                    request,
                    f'Journée de travail terminée à {WORK_END_LABEL}. '
                    'Votre présence a été clôturée automatiquement.',
                )
                return redirect('login')

        return self.get_response(request)