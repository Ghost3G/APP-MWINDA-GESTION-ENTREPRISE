from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

# Seuls ces comptes peuvent créer / modifier / terminer / réouvrir / supprimer un projet
PROJECT_MANAGER_USERNAMES = frozenset({
    'ibrahim.japhete',   # Directeur Technique — Japhete Kuta
    'emmanuel.maki',     # Ass. Directeur Technique — Emmanuel Maki
})

# Responsables Commercial — voient TOUS les portefeuilles CRM + réassignation
COMMERCIAL_LEAD_USERNAMES = frozenset({
    'michelle.bukebo',   # Responsable Commercial — tous les CRM
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
    """Création / modification / clôture / suppression de projets : Japhete & Maki uniquement."""
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


def is_finance_staff(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "org_group", "") == "finance"
    )


def can_edit_finance(user):
    """Saisie / modification : équipe Finance, admin et tous les directeurs."""
    if not can_access_finance(user):
        return False
    if is_admin_user(user) or is_management_user(user):
        return True
    return is_finance_staff(user)


def can_manage_finance_closure(user):
    """Clôturer ou rouvrir une journée de caisse."""
    if not can_access_finance(user):
        return False
    return can_edit_finance(user) or is_management_user(user)


def is_commercial_staff(user):
    return bool(
        user
        and user.is_authenticated
        and getattr(user, "org_group", "") == "commercial"
    )


def can_access_crm(user):
    """Menu CRM : commerciaux + direction uniquement (pas les autres agents ni la finance seule)."""
    if not user or not user.is_authenticated:
        return False
    if is_management_user(user) or is_commercial_lead(user):
        return True
    return is_commercial_staff(user)


def can_access_finance_clients(user):
    """Base clients via Finance (équipe finance / direction) ou via CRM."""
    return can_access_crm(user) or can_access_finance(user)


def can_view_all_crm_clients(user):
    """
    Voir tous les portefeuilles.
    - Responsable Commercial (Michelle, etc.) : oui
    - Direction : oui
    - Agent commercial : non (uniquement le sien)
    """
    if not can_access_crm(user):
        return False
    if is_commercial_lead(user):
        return True
    return is_management_user(user)


def can_reassign_crm_client(user):
    """Changer le commercial propriétaire d'un client."""
    if not can_access_crm(user):
        return False
    return is_management_user(user) or is_commercial_lead(user) or is_admin_user(user)


def can_edit_crm_clients(user):
    """Créer / modifier des fiches clients (CRM commercial ou base Finance)."""
    if can_access_crm(user):
        if can_view_all_crm_clients(user):
            return True
        return is_commercial_staff(user)
    return can_edit_finance(user)


def can_edit_crm_client(user, client):
    """Modifier une fiche : propriétaire, lead/direction, ou finance."""
    if not can_edit_crm_clients(user):
        return False
    if can_view_all_crm_clients(user):
        return True
    if can_edit_finance(user) and not can_access_crm(user):
        return True
    if can_edit_finance(user) and is_management_user(user):
        return True
    return bool(client and client.commercial_owner_id == user.id)


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
