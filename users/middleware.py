from datetime import datetime, timedelta

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


class AgentSessionWorkdayMiddleware:
    """
    Empêche l'expiration de session des agents pendant la journée de travail.
    Une connexion du matin reste valide jusqu'à la fin de service du jour,
    même sans activité.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            from django.utils import timezone
            from .presence import is_presence_auto_close_target, work_end_datetime

            if is_presence_auto_close_target(user):
                local_now = timezone.localtime()
                work_end_dt = work_end_datetime(local_now.date())
                if work_end_dt is not None:
                    # Petite marge pour que la requête de fin de service déclenche la déconnexion.
                    keep_until = int((work_end_dt - local_now).total_seconds()) + 300
                    if keep_until > 0:
                        request.session.set_expiry(keep_until)

        return self.get_response(request)


class AgentWorkEndLogoutMiddleware:
    """
    À la fin de service (Africa/Kinshasa) : déconnecte les agents,
    complète leur présence. Directeurs / admin restent connectés jusqu'à minuit.
    Lun–Ven 17:30 · Samedi 13:00.
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
                close_open_session_for_user,
                should_force_agent_logout_now,
                work_schedule_for_day,
            )

            # Clôture la fiche présence (départ fin de service) sans effacer les connexions du jour.
            if should_force_agent_logout_now(user):
                day = timezone.localdate()
                schedule = work_schedule_for_day(day)
                end_label = schedule.end_label if schedule.is_open else '17:30'
                close_open_session_for_user(user, day=day)
                logout(request)
                messages.info(
                    request,
                    f'Journée de travail terminée à {end_label}. '
                    'Vos heures de connexion du jour ont été conservées et le départ '
                    f'a été enregistré à {end_label}.',
                )
                return redirect('login')

        return self.get_response(request)


class MidnightLogoutMiddleware:
    """
    À minuit (00:00, Africa/Kinshasa) : déconnecte tout le monde pour une nouvelle journée.
    Complète la présence (départ enregistré à 00:00) et invalide la session Django.
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
                close_open_session_for_user_at_midnight,
                should_force_midnight_logout_now,
            )

            if should_force_midnight_logout_now(user):
                from .presence import MIDNIGHT_LOGOUT_LABEL

                yesterday = timezone.localdate() - timedelta(days=1)
                close_open_session_for_user_at_midnight(user, day=yesterday)
                logout(request)
                messages.info(
                    request,
                    'Nouvelle journée — veuillez vous reconnecter. '
                    f'Votre départ a été enregistré à {MIDNIGHT_LOGOUT_LABEL}.',
                )
                return redirect('login')

        return self.get_response(request)