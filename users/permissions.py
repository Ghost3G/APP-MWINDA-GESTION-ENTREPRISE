from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def is_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == "admin"))


def is_management_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in {"admin", "directeur"}))


def can_access_finance(user):
    """Direction + équipe Finance (comptable, etc.)."""
    if not user or not user.is_authenticated:
        return False
    if is_management_user(user):
        return True
    return getattr(user, "org_group", "") == "finance"


def admin_required(view_func):
    """Accès réservé aux administrateurs."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not is_admin_user(request.user):
            return HttpResponseForbidden("Vous n'avez pas l'accès administrateur")
        return view_func(request, *args, **kwargs)

    return wrapper


def management_required(view_func):
    """Accès réservé à la direction (admin + directeur)."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not is_management_user(request.user):
            return HttpResponseForbidden("Vous n'avez pas la permission de gérer cette ressource.")
        return view_func(request, *args, **kwargs)

    return wrapper
