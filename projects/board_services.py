from django.contrib.auth import get_user_model
from django.db.models import Prefetch, Q
from django.utils import timezone

from users.permissions import is_management_user

from .models import (
    Project,
    ProjectTask,
    TaskAttachment,
    TaskChecklist,
    TaskChecklistItem,
    TaskComment,
    TaskLabel,
)

User = get_user_model()

DEFAULT_LABELS = [
    ('Urgent', '#ef4444'),
    ('Design', '#a78bfa'),
    ('Production', '#60a5fa'),
    ('Client', '#22c55e'),
    ('Qualité', '#fde047'),
    ('Livraison', '#f97316'),
]


def seed_task_labels():
    for name, color in DEFAULT_LABELS:
        TaskLabel.objects.get_or_create(name=name, defaults={'color': color})


def _user_brief(user):
    return {
        'id': user.id,
        'name': user.get_labeled_name(),
        'short_name': user.get_display_name(),
        'title': user.get_title_label(),
        'initial': user.get_avatar_initial(),
        'avatar_url': user.avatar_url,
        'username': user.username,
    }


def can_access_project(user, project):
    if is_management_user(user):
        return True
    if project.manager_id == user.id:
        return True
    if project.technical_director_id == user.id:
        return True
    if project.commercial_agent_id == user.id:
        return True
    return project.members.filter(id=user.id).exists()


def can_access_task(user, task):
    if can_access_project(user, task.project):
        return True
    if task.assigned_to_id == user.id:
        return True
    return task.members.filter(id=user.id).exists()


def can_edit_task(user, task):
    if is_management_user(user):
        return True
    if task.project.manager_id == user.id:
        return True
    if task.project.technical_director_id == user.id:
        return True
    if task.assigned_to_id == user.id:
        return True
    return task.members.filter(id=user.id).exists()


def can_create_board_task(user, project):
    """Création de cartes : direction ou responsable suivi du projet."""
    if is_management_user(user):
        return True
    return bool(project and project.manager_id == user.id)


def accessible_projects(user):
    if is_management_user(user):
        return Project.objects.order_by('created_at', 'id')
    return Project.objects.filter(
        Q(members=user)
        | Q(manager=user)
        | Q(technical_director=user)
        | Q(commercial_agent=user)
    ).distinct().order_by('created_at', 'id')


def board_tasks_queryset(project):
    return ProjectTask.objects.filter(project=project).select_related(
        'assigned_to', 'project'
    ).prefetch_related(
        'members',
        'labels',
        Prefetch('comments', queryset=TaskComment.objects.select_related('author').order_by('created_at')),
        Prefetch('checklists', queryset=TaskChecklist.objects.prefetch_related(
            Prefetch('items', queryset=TaskChecklistItem.objects.order_by('order', 'id'))
        ).order_by('order', 'id')),
        Prefetch('attachments', queryset=TaskAttachment.objects.select_related('uploaded_by').order_by('-created_at')),
    ).order_by('order', 'id')


def serialize_checklist_item(item):
    return {
        'id': item.id,
        'text': item.text,
        'is_done': item.is_done,
        'order': item.order,
    }


def serialize_checklist(checklist):
    items = list(checklist.items.all())
    done_count = sum(1 for item in items if item.is_done)
    return {
        'id': checklist.id,
        'title': checklist.title,
        'order': checklist.order,
        'items': [serialize_checklist_item(item) for item in items],
        'progress': f"{done_count}/{len(items)}" if items else '0/0',
    }


def serialize_comment(comment):
    return {
        'id': comment.id,
        'content': comment.content,
        'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
        'author': _user_brief(comment.author),
    }


def serialize_attachment(attachment):
    return {
        'id': attachment.id,
        'name': attachment.original_name or attachment.file.name.split('/')[-1],
        'url': attachment.file.url,
        'created_at': attachment.created_at.strftime('%d/%m/%Y %H:%M'),
        'uploaded_by': _user_brief(attachment.uploaded_by),
    }


def serialize_task(task, include_details=False):
    members = list(task.members.all())
    member_set = {task.assigned_to_id}
    member_set.update(user.id for user in members)
    all_member_users = [task.assigned_to] + [user for user in members if user.id != task.assigned_to_id]

    checklist_data = []
    comments_data = []
    attachments_data = []
    if include_details:
        checklist_data = [serialize_checklist(checklist) for checklist in task.checklists.all()]
        comments_data = [serialize_comment(comment) for comment in task.comments.all()]
        attachments_data = [serialize_attachment(attachment) for attachment in task.attachments.all()]

    checklist_progress = '0/0'
    if include_details and checklist_data:
        total_items = sum(len(checklist['items']) for checklist in checklist_data)
        done_items = sum(
            sum(1 for item in checklist['items'] if item['is_done'])
            for checklist in checklist_data
        )
        checklist_progress = f"{done_items}/{total_items}"

    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'status_label': task.get_status_display(),
        'department': task.department,
        'department_label': task.get_department_display_label(),
        'due_date': task.due_date.isoformat() if task.due_date else '',
        'due_date_label': task.due_date.strftime('%d/%m/%Y') if task.due_date else '',
        'is_overdue': bool(
            task.due_date and task.status != 'done' and task.due_date < timezone.localdate()
        ),
        'assigned_to': _user_brief(task.assigned_to),
        'members': [_user_brief(user) for user in all_member_users],
        'member_ids': list(member_set),
        'labels': [{'id': label.id, 'name': label.name, 'color': label.color} for label in task.labels.all()],
        'label_ids': [label.id for label in task.labels.all()],
        'comments_count': task.comments.count() if not include_details else len(comments_data),
        'attachments_count': task.attachments.count() if not include_details else len(attachments_data),
        'checklist_progress': checklist_progress,
        'project_id': task.project_id,
        'project_name': task.project.name,
        'created_at': task.created_at.isoformat(),
        'created_at_label': task.created_at.strftime('%d/%m/%Y'),
        'updated_at': task.updated_at.isoformat(),
        'comments': comments_data,
        'checklists': checklist_data,
        'attachments': attachments_data,
    }


def board_columns(tasks):
    columns = {
        'pending': [],
        'in_progress': [],
        'done': [],
    }
    for task in tasks:
        if task.status in columns:
            columns[task.status].append(serialize_task(task))
    return columns
