"""
URL configuration for AppMwinda project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from projects.views import (
    dashboard,
    admin_dashboard,
    admin_users,
    admin_projects,
    admin_messages,
    admin_reports,
    admin_audit_logs,
    admin_create_user,
    manage_tasks,
)
from users.views import login_view, logout_view, profile_view
from users.notifications import notifications_feed, notifications_mark_read, dismiss_onboarding
from users.setup import setup_view

urlpatterns = [
    path('admin/django/', admin.site.urls),
    path('setup/', setup_view, name='setup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('api/notifications/', notifications_feed, name='notifications_feed'),
    path('api/notifications/mark-read/', notifications_mark_read, name='notifications_mark_read'),
    path('api/onboarding/dismiss/', dismiss_onboarding, name='dismiss_onboarding'),
    path('', dashboard, name='dashboard'),
    path('messaging/', include('messaging.urls')),
    path('projects/', include('projects.urls')),
    path('reports/', include('reports.urls')),
    path('users/', include('users.urls')),
    path('stock/', include('inventory.urls')),
    path('tasks/', manage_tasks, name='manage_tasks'),
    
    # Admin panel
    path('admin/', admin_dashboard, name='admin_dashboard'),
    path('admin/users/', admin_users, name='admin_users'),
    path('admin/users/create/', admin_create_user, name='admin_create_user'),
    path('admin/projects/', admin_projects, name='admin_projects'),
    path('admin/messages/', admin_messages, name='admin_messages'),
    path('admin/reports/', admin_reports, name='admin_reports'),
    path('admin/audit-logs/', admin_audit_logs, name='admin_audit_logs'),
]

# Endpoints de debug: exposés uniquement en environnement DEBUG
if settings.DEBUG:
    from users.setup import quick_admin_create
    from users.debug import debug_status

    urlpatterns += [
        path('debug/status/', debug_status, name='debug_status'),
        path('api/quick-admin-create/', quick_admin_create, name='quick_admin_create'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
