"""Permissions module Ressources humaines."""
from users.permissions import is_admin_user, is_management_user

HR_MANAGER_USERNAMES = frozenset({
    'bertin.musila',
})


def is_hr_manager(user):
    """DRH / admin : validation congés, documents, vue RH élargie."""
    if not user or not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    username = (user.username or '').strip().lower()
    if username in HR_MANAGER_USERNAMES:
        return True
    org = (getattr(user, 'org_group', '') or '').strip().lower()
    title = (getattr(user, 'job_title', '') or '').strip().lower()
    return org == 'rh' or 'drh' in title


def can_manage_hr_documents(user):
    return is_hr_manager(user)


def can_review_leaves(user):
    return is_hr_manager(user)


def can_view_hr_staff_directory(user):
    """Effectif visible à tous les connectés ; édition via Départements/admin."""
    return bool(user and user.is_authenticated)


def can_view_all_hr_presence(user):
    return is_management_user(user) or is_hr_manager(user)
