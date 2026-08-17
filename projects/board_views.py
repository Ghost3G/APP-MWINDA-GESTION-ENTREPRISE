from django.utils import timezone

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .board_services import (
    accessible_projects,
    board_columns,
    board_tasks_queryset,
    can_access_project,
    can_access_task,
    can_create_board_task,
    can_edit_task,
    seed_task_labels,
    serialize_task,
)
from .models import (
    Project,
    ProjectTask,
    TaskAttachment,
    TaskChecklist,
    TaskChecklistItem,
    TaskComment,
    TaskLabel,
)
from .task_services import create_project_task, set_task_status, notify_task_assignment
from users.security import write_audit_log
from users.uploads import safe_filename, validate_attachment_upload

User = get_user_model()

MAX_COMMENT_LENGTH = 2000


def _get_project_or_403(user, project_id):
    if not project_id:
        return None
    try:
        project = Project.objects.get(id=project_id)
    except (Project.DoesNotExist, ValueError, TypeError):
        return None
    if not can_access_project(user, project):
        return None
    return project


def _json_error(message, status=400):
    return JsonResponse({'ok': False, 'error': message}, status=status)


@login_required(login_url='login')
def task_board(request):
    seed_task_labels()
    projects = accessible_projects(request.user)
    project_id = request.GET.get('project_id', '').strip()
    view_mode = request.GET.get('view', 'board').strip() or 'board'
    if view_mode not in {'board', 'calendar', 'timeline'}:
        view_mode = 'board'

    selected_project = projects.first()
    if project_id:
        selected_project = projects.filter(id=project_id).first() or selected_project

    tasks = []
    columns = {'pending': [], 'in_progress': [], 'done': []}
    project_members = []
    if selected_project:
        tasks_qs = board_tasks_queryset(selected_project)
        tasks = [serialize_task(task) for task in tasks_qs]
        columns = board_columns(tasks_qs)
        project_members = selected_project.get_stakeholders()

    context = {
        'projects': projects,
        'selected_project': selected_project,
        'selected_project_id': selected_project.id if selected_project else '',
        'view_mode': view_mode,
        'tasks_json': json.dumps(tasks),
        'columns_json': json.dumps(columns),
        'labels': TaskLabel.objects.all(),
        'labels_json': json.dumps([
            {'id': label.id, 'name': label.name, 'color': label.color}
            for label in TaskLabel.objects.all()
        ]),
        'project_members': project_members,
        'members_json': json.dumps([
            {
                'id': user.id,
                'name': user.get_labeled_name(),
                'initial': user.get_avatar_initial(),
                'avatar_url': user.avatar_url,
            }
            for user in project_members
        ]),
        'status_choices': ProjectTask.STATUS_CHOICES,
        'can_create': bool(selected_project and can_create_board_task(request.user, selected_project)),
    }
    from reports.chart_data import build_task_board_charts

    context['mw_charts'] = (
        build_task_board_charts(
            columns,
            project_name=selected_project.name if selected_project else '',
        )
        if selected_project
        else []
    )
    return render(request, 'task_board.html', context)


@login_required(login_url='login')
@require_GET
def board_task_detail(request, task_id):
    task = get_object_or_404(
        ProjectTask.objects.select_related('assigned_to', 'project').prefetch_related(
            'members', 'labels',
            'comments__author',
            'checklists__items',
            'attachments__uploaded_by',
        ),
        id=task_id,
    )
    if not can_access_task(request.user, task):
        return _json_error('Accès refusé', 403)
    return JsonResponse({'ok': True, 'task': serialize_task(task, include_details=True)})


@login_required(login_url='login')
@require_POST
def board_update_status(request, task_id):
    task = get_object_or_404(ProjectTask.objects.select_related('project'), id=task_id)
    if not can_edit_task(request.user, task):
        return _json_error('Permission refusée', 403)

    status = request.POST.get('status', '').strip()
    if status not in dict(ProjectTask.STATUS_CHOICES):
        return _json_error('Statut invalide')

    set_task_status(task, status)
    task.refresh_from_db()
    write_audit_log(
        request.user,
        'board_status_change',
        path=request.path,
        method='POST',
        metadata={'task_id': task.id, 'project_id': task.project_id, 'status': status},
    )
    return JsonResponse({'ok': True, 'task': serialize_task(task)})


@login_required(login_url='login')
@require_POST
def board_update_task(request, task_id):
    task = get_object_or_404(
        ProjectTask.objects.select_related('project', 'assigned_to').prefetch_related('members', 'labels'),
        id=task_id,
    )
    if not can_edit_task(request.user, task):
        return _json_error('Permission refusée', 403)

    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    due_date = request.POST.get('due_date', '').strip()
    label_ids = request.POST.getlist('label_ids')
    member_ids = request.POST.getlist('member_ids')

    if title:
        task.title = title
    task.description = description

    if due_date:
        from datetime import datetime
        try:
            task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
        except ValueError:
            return _json_error('Date invalide')
    else:
        task.due_date = None

    task.save()

    valid_labels = TaskLabel.objects.filter(id__in=label_ids)
    task.labels.set(valid_labels)

    previous_member_ids = set(task.members.values_list('id', flat=True))
    previous_assignee_id = task.assigned_to_id
    valid_members = task.project.members.filter(id__in=member_ids)
    task.members.set(valid_members)
    if member_ids and task.assigned_to_id not in [int(member_id) for member_id in member_ids if member_id.isdigit()]:
        first_member = valid_members.first()
        if first_member:
            task.assigned_to = first_member
            task.save(update_fields=['assigned_to'])

    newly_added = [member for member in valid_members if member.id not in previous_member_ids]
    if task.assigned_to_id != previous_assignee_id and task.assigned_to:
        newly_added.append(task.assigned_to)
    if newly_added:
        notify_task_assignment(task, actor=request.user, users=newly_added)

    task.refresh_from_db()
    return JsonResponse({'ok': True, 'task': serialize_task(task, include_details=True)})


@login_required(login_url='login')
@require_POST
def board_add_comment(request, task_id):
    task = get_object_or_404(ProjectTask.objects.select_related('project'), id=task_id)
    if not can_access_task(request.user, task):
        return _json_error('Permission refusée', 403)

    content = request.POST.get('content', '').strip()
    if not content:
        return _json_error('Commentaire vide')
    if len(content) > MAX_COMMENT_LENGTH:
        return _json_error(f'Commentaire trop long (max {MAX_COMMENT_LENGTH} caractères)')

    comment = TaskComment.objects.create(task=task, author=request.user, content=content)
    from .board_services import serialize_comment
    return JsonResponse({'ok': True, 'comment': serialize_comment(comment)})


@login_required(login_url='login')
@require_POST
def board_add_checklist(request, task_id):
    task = get_object_or_404(ProjectTask.objects.select_related('project'), id=task_id)
    if not can_edit_task(request.user, task):
        return _json_error('Permission refusée', 403)

    title = request.POST.get('title', '').strip() or 'Liste de contrôle'
    checklist = TaskChecklist.objects.create(task=task, title=title)
    from .board_services import serialize_checklist
    return JsonResponse({'ok': True, 'checklist': serialize_checklist(checklist)})


@login_required(login_url='login')
@require_POST
def board_add_checklist_item(request, checklist_id):
    checklist = get_object_or_404(TaskChecklist.objects.select_related('task__project'), id=checklist_id)
    if not can_edit_task(request.user, checklist.task):
        return _json_error('Permission refusée', 403)

    text = request.POST.get('text', '').strip()
    if not text:
        return _json_error('Texte requis')

    item = TaskChecklistItem.objects.create(checklist=checklist, text=text)
    from .board_services import serialize_checklist_item
    return JsonResponse({'ok': True, 'item': serialize_checklist_item(item)})


@login_required(login_url='login')
@require_POST
def board_toggle_checklist_item(request, item_id):
    item = get_object_or_404(
        TaskChecklistItem.objects.select_related('checklist__task__project'),
        id=item_id,
    )
    if not can_edit_task(request.user, item.checklist.task):
        return _json_error('Permission refusée', 403)

    item.is_done = not item.is_done
    item.save(update_fields=['is_done'])
    from .board_services import serialize_checklist_item
    return JsonResponse({'ok': True, 'item': serialize_checklist_item(item)})


@login_required(login_url='login')
@require_POST
def board_upload_attachment(request, task_id):
    task = get_object_or_404(ProjectTask.objects.select_related('project'), id=task_id)
    if not can_edit_task(request.user, task):
        return _json_error('Permission refusée', 403)

    upload = request.FILES.get('file')
    if not upload:
        return _json_error('Fichier manquant')
    upload_error = validate_attachment_upload(upload)
    if upload_error:
        return _json_error(upload_error)

    attachment = TaskAttachment.objects.create(
        task=task,
        uploaded_by=request.user,
        file=upload,
        original_name=safe_filename(upload.name),
    )
    from .board_services import serialize_attachment
    return JsonResponse({'ok': True, 'attachment': serialize_attachment(attachment)})


@login_required(login_url='login')
@require_POST
def board_create_task(request):
    project_id = request.POST.get('project_id', '').strip()
    title = request.POST.get('title', '').strip()
    assigned_to_id = request.POST.get('assigned_to_id', '').strip()
    department = request.POST.get('department', '').strip()
    due_date = request.POST.get('due_date', '').strip()

    project = _get_project_or_403(request.user, project_id)
    if not project:
        return _json_error('Projet inaccessible', 403)

    if not can_create_board_task(request.user, project):
        return _json_error('Permission refusée', 403)

    if not title or not assigned_to_id:
        return _json_error('Titre et membre requis')

    try:
        assignee = User.objects.get(id=assigned_to_id, is_active=True)
    except (User.DoesNotExist, ValueError, TypeError):
        return _json_error('Membre introuvable')

    stakeholder_ids = {
        project.manager_id,
        project.technical_director_id,
        project.commercial_agent_id,
    }
    if (
        not project.members.filter(id=assignee.id).exists()
        and assignee.id not in stakeholder_ids
    ):
        return _json_error("Le membre doit faire partie du projet")

    task = create_project_task(
        project,
        assignee,
        title,
        department or project.branch,
        status='pending',
        actor=request.user,
    )
    if due_date:
        from datetime import datetime
        try:
            task.due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
            task.save(update_fields=['due_date'])
        except ValueError:
            pass

    write_audit_log(
        request.user,
        'board_create_task',
        path=request.path,
        method='POST',
        metadata={'task_id': task.id, 'project_id': project.id, 'assigned_to': assignee.id},
    )
    return JsonResponse({'ok': True, 'task': serialize_task(task)})
