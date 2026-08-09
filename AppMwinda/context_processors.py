def app_notifications(request):
    if not request.user.is_authenticated:
        return {
            'unread_messages_count': 0,
            'unread_project_assignments': 0,
            'unread_task_assignments': 0,
            'unread_notifications_total': 0,
            'is_management': False,
            'is_admin': False,
            'is_finance': False,
            'is_crm': False,
            'current_user_profile': None,
            'project_deadline_alerts': [],
            'agent_logout_warning': {
                'enabled': False,
                'active': False,
                'warn_label': '17:00',
                'logout_label': '17:30',
                'seconds_remaining': 0,
                'server_now_iso': '',
                'logout_at_iso': '',
                'warn_at_iso': '',
            },
            'service_hours': {
                'weekday_label': 'Lundi – Vendredi : 08:30 – 17:30',
                'saturday_label': 'Samedi : 09:00 – 13:00',
                'sunday_label': 'Dimanche : fermé',
                'summary_label': 'Lun–Ven 08:30–17:30 · Sam 09:00–13:00',
                'today_open': True,
                'today_name': '',
                'today_short': '08:30 – 17:30',
                'today_range': 'Lundi – Vendredi : 08:30 – 17:30',
                'today_start': '08:30',
                'today_end': '17:30',
            },
        }

    from datetime import timedelta

    from django.db import OperationalError, ProgrammingError
    from django.db.models import Q
    from django.utils import timezone

    from messaging.models import Message
    from projects.models import Project, ProjectAssignmentNotification, TaskAssignmentNotification
    from users.permissions import (
        is_admin_user,
        is_management_user,
        can_access_finance,
        can_access_crm,
    )
    from users.presence import agent_logout_warning_payload, service_hours_banner_payload

    unread_messages_count = 0
    unread_project_assignments = 0
    unread_task_assignments = 0
    project_deadline_alerts = []

    user = request.user
    is_management = is_management_user(user)
    is_admin = is_admin_user(user)
    is_finance = can_access_finance(user)
    is_crm = can_access_crm(user)
    agent_logout_warning = agent_logout_warning_payload(user)
    service_hours = service_hours_banner_payload()

    try:
        unread_messages_count = (
            Message.objects.filter(receiver=request.user, is_read=False)
            .only('id')
            .count()
        )
        unread_project_assignments = (
            ProjectAssignmentNotification.objects.filter(user=request.user, is_read=False)
            .only('id')
            .count()
        )
        unread_task_assignments = (
            TaskAssignmentNotification.objects.filter(user=request.user, is_read=False)
            .only('id')
            .count()
        )

        # Bandeau rouge : projets non terminés avec échéance ≤ 2 jours (ou en retard)
        today = timezone.localdate()
        soon_limit = today + timedelta(days=2)
        projects_qs = Project.objects.exclude(status='done').filter(end_date__lte=soon_limit)
        if not is_management and not user.is_superuser:
            projects_qs = projects_qs.filter(
                Q(members=user)
                | Q(manager=user)
                | Q(technical_director=user)
                | Q(commercial_agent=user)
            ).distinct()

        for project in projects_qs.order_by('end_date', 'name')[:20]:
            days_left = (project.end_date - today).days
            if days_left < 0:
                label = (
                    f'EN RETARD — {project.name} — échéance '
                    f'{project.end_date.strftime("%d/%m/%Y")} '
                    f'({abs(days_left)} j)'
                )
                level = 'overdue'
            elif days_left == 0:
                label = (
                    f'ÉCHÉANCE AUJOURD’HUI — {project.name} — '
                    f'{project.end_date.strftime("%d/%m/%Y")}'
                )
                level = 'overdue'
            else:
                label = (
                    f'ÉCHÉANCE PROCHE — {project.name} — '
                    f'{project.end_date.strftime("%d/%m/%Y")} '
                    f'(dans {days_left} j)'
                )
                level = 'soon'
            project_deadline_alerts.append({
                'id': project.id,
                'name': project.name,
                'end_date': project.end_date,
                'days_left': days_left,
                'label': label,
                'level': level,
                'url': f'/projects/{project.id}/',
            })
    except (OperationalError, ProgrammingError):
        pass

    unread_notifications_total = (
        unread_messages_count + unread_project_assignments + unread_task_assignments
    )

    return {
        'unread_messages_count': unread_messages_count,
        'unread_project_assignments': unread_project_assignments,
        'unread_task_assignments': unread_task_assignments,
        'unread_notifications_total': unread_notifications_total,
        'is_management': is_management,
        'is_admin': is_admin,
        'is_finance': is_finance,
        'is_crm': is_crm,
        'project_deadline_alerts': project_deadline_alerts,
        'agent_logout_warning': agent_logout_warning,
        'service_hours': service_hours,
        'current_user_profile': {
            'display_name': user.get_labeled_name(),
            'short_name': user.get_display_name(),
            'title_label': user.get_title_label(),
            'initial': user.get_avatar_initial(),
            'avatar_url': user.avatar_url,
            'role_display': user.get_role_display(),
            'department_display': user.get_org_group_display(),
            'org_group_display': user.get_org_group_display(),
            'job_title': user.job_title,
            'grade': user.grade,
            'department_name': user.department_name,
            'branch_display': user.get_direction_display(),
            'username': user.username,
        },
    }
