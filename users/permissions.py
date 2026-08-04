from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

# Seuls ces comptes peuvent créer / modifier / terminer / réouvrir un projet
PROJECT_MANAGER_USERNAMES = frozenset({
    'ibrahim.japhete',   # Directeur Technique — Japhete Kuta
    'emmanuel.maki',     # Ass. Directeur Technique — Emmanuel Maki
})

# Responsables Commercial — notifiés à chaque projet avec agent commercial
COMMERCIAL_LEAD_USERNAMES = frozenset({
    'michelle.bukebo',   # Responsable Commercial (sans Finance)
    'michael.kabale',    # Chef Responsable Commercial (= accès DG)
})
# Alias rétrocompatibilité
COMMERCIAL_LEAD_USERNAME = 'michelle.bukebo'

# Agents Logistique — notifiés quand un projet passe en attente de livraison
LOGISTICS_NOTIFY_USERNAMES = frozenset({
    'joseph.mbuyu',  # Joseph Mbuyu — Agent Logistique
})

# Accès Finance retiré uniquement pour ces comptes (pas le Chef / DG)
COMMERCIAL_NO_FINANCE_USERNAMES = frozenset({
    'michelle.bukebo',
})


def is_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == "admin"))


def is_management_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in {"admin", "directeur"}))


def can_manage_projects(user):
    """Création / modification / clôture de projets : Japhete Kuta & Emmanuel Maki uniquement."""
    if not user or not user.is_authenticated:
        return False
    return (user.username or '').strip().lower() in PROJECT_MANAGER_USERNAMES


def is_commercial_lead(user):
    if not user or not user.is_authenticated:
        return False
    return (user.username or '').strip().lower() in COMMERCIAL_LEAD_USERNAMES


def can_access_finance(user):
    """Direction + équipe Finance (comptable, etc.). Michelle Bukebo : exclue."""
    if not user or not user.is_authenticated:
        return False
    if (user.username or '').strip().lower() in COMMERCIAL_NO_FINANCE_USERNAMES:
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
