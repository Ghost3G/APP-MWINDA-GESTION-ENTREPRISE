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
