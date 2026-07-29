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
            'current_user_profile': None,
        }

    from django.db import OperationalError, ProgrammingError

    from messaging.models import Message
    from projects.models import ProjectAssignmentNotification, TaskAssignmentNotification
    from users.permissions import is_admin_user, is_management_user, can_access_finance

    unread_messages_count = 0
    unread_project_assignments = 0
    unread_task_assignments = 0

    try:
        # 1 requête messages + 2 counts notifications (indexés)
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
    except (OperationalError, ProgrammingError):
        pass

    user = request.user
    is_management = is_management_user(user)
    is_admin = is_admin_user(user)
    is_finance = can_access_finance(user)
    unread_notifications_total = unread_messages_count + unread_project_assignments + unread_task_assignments

    return {
        'unread_messages_count': unread_messages_count,
        'unread_project_assignments': unread_project_assignments,
        'unread_task_assignments': unread_task_assignments,
        'unread_notifications_total': unread_notifications_total,
        'is_management': is_management,
        'is_admin': is_admin,
        'is_finance': is_finance,
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
