"""
Debug views to diagnose setup issues on Render.
Restricted: staff / superuser only, and only when DEBUG is on
or DEBUG_STATUS_TOKEN matches ?token=.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponseForbidden
from django.shortcuts import render

User = get_user_model()


def debug_status(request):
    """Show database and auth status (protected)."""
    token = (request.GET.get('token') or '').strip()
    expected = (getattr(settings, 'DEBUG_STATUS_TOKEN', '') or '').strip()
    allowed = (
        settings.DEBUG
        or (request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff))
        or (expected and token and token == expected)
    )
    if not allowed:
        return HttpResponseForbidden('Accès refusé.')

    all_users = list(User.objects.all().values('username', 'email', 'is_superuser', 'is_staff', 'role'))
    admin_users = list(User.objects.filter(is_superuser=True).values('username', 'email'))

    db_info = {
        'engine': connection.settings_dict.get('ENGINE', 'unknown'),
        'name': connection.settings_dict.get('NAME', 'unknown'),
    }

    context = {
        'all_users': all_users,
        'admin_users': admin_users,
        'admin_count': len(admin_users),
        'total_user_count': len(all_users),
        'db_info': db_info,
        'auth_user_model': settings.AUTH_USER_MODEL,
        'user_table_exists': 'users_user' in connection.introspection.table_names(),
    }

    return render(request, 'debug_status.html', context)
