"""Notifications liées aux affectations projets / commercial."""
from django.contrib.auth import get_user_model

from users.permissions import COMMERCIAL_LEAD_USERNAMES

from .models import ProjectAssignmentNotification

User = get_user_model()


def notify_project_assignment(user, project):
    if not user or not project:
        return
    notif, created = ProjectAssignmentNotification.objects.get_or_create(
        user=user,
        project=project,
        defaults={'is_read': False},
    )
    # Nouvelle affectation (ou commercial changé) → cloche à nouveau
    if not created and notif.is_read:
        notif.is_read = False
        notif.save(update_fields=['is_read'])


def notify_commercial_on_project(project, *, actor=None, members=None):
    """
    Informe :
    - chaque membre / stakeholder passé dans members
    - l'agent commercial du projet
    - les responsables commercial (Michelle + Chef Michael), dès qu'un commercial est lié
    """
    recipients = []
    if members:
        recipients.extend([m for m in members if m])

    if project.commercial_agent:
        recipients.append(project.commercial_agent)

    if project.commercial_agent_id:
        leads = User.objects.filter(username__in=COMMERCIAL_LEAD_USERNAMES)
        recipients.extend(list(leads))

    seen = set()
    actor_id = getattr(actor, 'id', None)
    for user in recipients:
        if not user or user.id in seen:
            continue
        if actor_id and user.id == actor_id:
            continue
        seen.add(user.id)
        notify_project_assignment(user, project)
