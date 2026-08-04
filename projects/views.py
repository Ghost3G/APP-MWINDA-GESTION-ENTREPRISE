from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Count, Q
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from .board_services import accessible_projects, can_access_project
from .models import Project
from .models import AgentTimeEntry, ProjectAssignmentNotification, ProjectTask, TaskAssignmentNotification
from .branches import TECH_BRANCH_CHOICES, TECH_DEPARTMENT_LABEL, normalize_branch, is_valid_branch
from .task_services import (
    DEPARTMENT_TASK_TEMPLATES,
    ensure_project_tasks,
    get_task_for_user,
    set_task_status,
    build_dashboard_tasks,
    create_project_task,
    apply_department_template,
    update_project_task,
    notify_task_assignment,
)
from .assignment import ai_available, apply_smart_project_plan
from .project_notifications import notify_commercial_on_project
from reports.models import DailyReport
from messaging.models import Message
from django.contrib.auth import get_user_model
from users.models import AuditLog
from users.notifications import get_due_soon_tasks, get_overdue_tasks
from users.permissions import admin_required, is_admin_user, is_management_user, management_required, can_manage_projects
from users.security import write_audit_log
from users.uploads import validate_image_upload

User = get_user_model()


def _format_seconds(total_seconds):
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


FRENCH_MONTHS = (
    '',
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
)


def _group_completed_projects_by_month(projects):
    """Regroupe les projets terminés par mois (date de fin), plus récents d’abord."""
    ordered = list(projects.order_by('-end_date', '-id'))
    groups = []
    index = {}
    for project in ordered:
        end = project.end_date
        if end:
            key = f'{end.year}-{end.month:02d}'
            label = f'{FRENCH_MONTHS[end.month]} {end.year}'
            sort_key = (end.year, end.month)
        else:
            key = 'sans-date'
            label = 'Sans date de fin'
            sort_key = (0, 0)
        if key not in index:
            index[key] = len(groups)
            groups.append({
                'key': key,
                'label': label,
                'sort_key': sort_key,
                'projects': [],
            })
        groups[index[key]]['projects'].append(project)

    groups.sort(key=lambda item: item['sort_key'], reverse=True)
    for group in groups:
        group['count'] = len(group['projects'])
        group.pop('sort_key', None)
    return groups


def _build_current_project_card(project, empty_title='Aucun projet en cours', empty_description='', kicker='Projet en cours'):
    """Payload Accueil : aperçu + photo du projet en cours."""
    if not project:
        return {
            'id': None,
            'title': empty_title,
            'description': empty_description or 'Aucun projet actif pour le moment.',
            'button_text': 'VOIR LES PROJETS',
            'status_display': '',
            'cover_url': '',
            'branch': '',
            'start_date': '',
            'end_date': '',
            'manager_name': '',
            'members_count': 0,
            'detail_url': '',
            'kicker': kicker,
            'home_order': 0,
        }

    description = (project.description or '').strip()
    if len(description) > 160:
        description = description[:157].rstrip() + '…'

    return {
        'id': project.id,
        'title': project.name,
        'description': description or 'Aucune description.',
        'button_text': 'OUVRIR',
        'status_display': project.get_status_display(),
        'cover_url': project.cover_url,
        'branch': project.get_branch_display_label(),
        'start_date': project.start_date.strftime('%d/%m/%Y') if project.start_date else '',
        'end_date': project.end_date.strftime('%d/%m/%Y') if project.end_date else '',
        'manager_name': project.manager.get_labeled_name() if project.manager_id else '',
        'members_count': project.members.count(),
        'detail_url': f'/projects/{project.id}/',
        'kicker': kicker,
        'home_order': getattr(project, 'home_order', 0) or 0,
    }


HOME_FEATURED_MAX = 3


def _parse_home_feature(post_data):
    show = post_data.get('show_on_home') in {'1', 'on', 'true', 'True', 'yes'}
    raw_order = post_data.get('home_order', '1') or '1'
    try:
        order = int(raw_order)
    except (TypeError, ValueError):
        order = 1
    order = max(1, min(HOME_FEATURED_MAX, order))
    return show, order


def _next_free_home_order(exclude_project_id=None, preferred=1):
    """Choisit une position Accueil libre (1–3), en préférant preferred si dispo."""
    qs = Project.objects.filter(show_on_home=True)
    if exclude_project_id:
        qs = qs.exclude(pk=exclude_project_id)
    taken = set(qs.values_list('home_order', flat=True))
    preferred = max(1, min(HOME_FEATURED_MAX, int(preferred or 1)))
    if preferred not in taken:
        return preferred
    for order in range(1, HOME_FEATURED_MAX + 1):
        if order not in taken:
            return order
    return preferred


def _apply_home_feature(project, show_on_home, home_order=1):
    """
    Épingler / retirer un projet de l’Accueil (max 3 affichés).
    Ne bloque jamais la création du projet : si l’Accueil est plein,
    remplace uniquement la position demandée.
    """
    if not show_on_home:
        if project.show_on_home or project.home_order:
            project.show_on_home = False
            project.home_order = 0
            project.save(update_fields=['show_on_home', 'home_order'])
        return True, None

    others = Project.objects.filter(show_on_home=True).exclude(pk=project.pk)
    others_count = others.count()
    preferred = max(1, min(HOME_FEATURED_MAX, int(home_order or 1)))

    if others_count >= HOME_FEATURED_MAX:
        # Accueil plein : on remplace la position choisie (le projet reste créé).
        Project.objects.filter(show_on_home=True, home_order=preferred).exclude(pk=project.pk).update(
            show_on_home=False,
            home_order=0,
        )
        final_order = preferred
        note = (
            f"L’Accueil est limité à {HOME_FEATURED_MAX} projets : "
            f"la position {final_order} a été mise à jour."
        )
    else:
        # Des places libres : on n’enlève personne, on prend un créneau libre.
        final_order = _next_free_home_order(exclude_project_id=project.pk, preferred=preferred)
        note = None

    project.show_on_home = True
    project.home_order = final_order
    project.save(update_fields=['show_on_home', 'home_order'])
    return True, note


def _resolve_home_project_cards(
    user,
    fallback_candidates,
    *,
    empty_title='Aucun projet en cours',
    empty_description='',
):
    """
    Cartes Accueil : projets épinglés (1–3), sinon repli automatique (1 carte).
    Les agents ne voient que les projets auxquels ils ont accès.
    """
    featured = list(
        Project.objects.filter(show_on_home=True)
        .select_related('manager')
        .prefetch_related('members')
        .order_by('home_order', 'created_at', 'id')[:HOME_FEATURED_MAX]
    )
    if featured and user is not None and not is_management_user(user):
        featured = [p for p in featured if can_access_project(user, p)][:HOME_FEATURED_MAX]
    if featured:
        cards = []
        for index, project in enumerate(featured, start=1):
            card = _build_current_project_card(
                project,
                kicker=f'Projet mis en avant · {index}',
            )
            card['home_order'] = project.home_order or index
            cards.append(card)
        return cards, cards[0]

    fallback = None
    for candidate in fallback_candidates:
        if candidate is None:
            continue
        if isinstance(candidate, Project):
            fallback = candidate
        elif hasattr(candidate, 'first'):
            fallback = candidate.first()
        if fallback:
            break

    card = _build_current_project_card(
        fallback,
        empty_title=empty_title,
        empty_description=empty_description,
    )
    return [card], card


def _entry_elapsed_seconds(entry, now):
    elapsed = int((now - entry.started_at).total_seconds())
    return entry.duration_seconds + max(elapsed, 0)


def _close_entry(entry, now):
    entry.duration_seconds = _entry_elapsed_seconds(entry, now)
    entry.ended_at = now
    entry.save(update_fields=['duration_seconds', 'ended_at'])


def _open_entry_for_user(user, entry_type):
    return AgentTimeEntry.objects.filter(
        user=user,
        entry_type=entry_type,
        ended_at__isnull=True,
    ).first()


def _ensure_work_session(user):
    try:
        if _open_entry_for_user(user, 'work'):
            return
        AgentTimeEntry.objects.create(
            user=user,
            entry_type='work',
            started_at=timezone.now(),
        )
    except Exception:
        # Silently continue if AgentTimeEntry creation fails (e.g., migrations not run)
        pass

def _is_management_user(user):
    return is_management_user(user)


def _commercial_agents_qs():
    return User.objects.filter(
        Q(org_group='commercial') | Q(grade__icontains='commercial') | Q(job_title__icontains='commercial')
    ).exclude(role='admin').distinct().order_by('first_name', 'username')


def _default_technical_director():
    return User.objects.filter(username='ibrahim.japhete').first()


def _default_project_manager():
    return User.objects.filter(username='emmanuel.maki').first()


def _project_stakeholders(project):
    return project.get_stakeholders()


def _handle_task_management_post(request, default_project_id=None):
    action = request.POST.get('action', '').strip()

    if action == 'create':
        project_id = request.POST.get('project_id', '').strip() or (str(default_project_id) if default_project_id else '')
        assigned_to_id = request.POST.get('assigned_to_id', '').strip()
        title = request.POST.get('title', '').strip()
        department = request.POST.get('department', '').strip()
        status = request.POST.get('status', 'pending').strip() or 'pending'
        due_date = request.POST.get('due_date', '').strip() or None

        if not all([project_id, assigned_to_id, title]):
            messages.error(request, "Projet, agent et titre de tâche sont requis.")
            return

        project = get_object_or_404(Project, id=project_id)
        assignee = get_object_or_404(User, id=assigned_to_id)

        if not project.members.filter(id=assignee.id).exists():
            messages.error(request, "L'agent doit être membre du projet sélectionné.")
            return

        valid_statuses = [value for value, _ in ProjectTask.STATUS_CHOICES]
        if status not in valid_statuses:
            status = 'pending'

        task = create_project_task(
            project,
            assignee,
            title,
            department=department or assignee.direction,
            status='pending',
            actor=request.user,
            due_date=due_date,
        )
        if status != 'pending':
            set_task_status(task, status)
        messages.success(request, f"Tâche « {task.title} » assignée à {assignee.get_labeled_name()}.")
        return

    if action == 'quick_status':
        task_id = request.POST.get('task_id', '').strip()
        status = request.POST.get('status', '').strip()
        task = get_object_or_404(ProjectTask, id=task_id)
        valid_statuses = [value for value, _ in ProjectTask.STATUS_CHOICES]
        if status not in valid_statuses:
            messages.error(request, "Statut invalide.")
            return
        set_task_status(task, status)
        messages.success(request, f"« {task.title} » → {task.get_status_display()}.")
        return

    if action == 'update':
        task_id = request.POST.get('task_id', '').strip()
        title = request.POST.get('title', '').strip()
        assigned_to_id = request.POST.get('assigned_to_id', '').strip()
        department = request.POST.get('department', '').strip()
        status = request.POST.get('status', '').strip()
        due_date_raw = request.POST.get('due_date', None)
        due_date = due_date_raw.strip() if isinstance(due_date_raw, str) else due_date_raw

        task = get_object_or_404(ProjectTask.objects.select_related('project'), id=task_id)
        assignee = task.assigned_to
        if assigned_to_id:
            assignee = get_object_or_404(User, id=assigned_to_id)
            if not task.project.members.filter(id=assignee.id).exists():
                messages.error(request, "Le nouvel agent doit être membre du projet.")
                return

        update_kwargs = {
            'title': title or task.title,
            'assigned_to': assignee,
            'department': department or task.department,
            'status': status or None,
            'actor': request.user,
        }
        if due_date_raw is not None:
            update_kwargs['due_date'] = due_date or None

        update_project_task(task, **update_kwargs)
        messages.success(request, "Tâche mise à jour.")
        return

    if action == 'delete':
        task_id = request.POST.get('task_id', '').strip()
        task = get_object_or_404(ProjectTask, id=task_id)
        title = task.title
        task.delete()
        messages.success(request, f"Tâche « {title} » supprimée.")
        return

    if action == 'apply_template':
        project_id = request.POST.get('project_id', '').strip() or (str(default_project_id) if default_project_id else '')
        assigned_to_id = request.POST.get('assigned_to_id', '').strip()
        department = request.POST.get('department', '').strip()

        project = get_object_or_404(Project, id=project_id)
        assignee = get_object_or_404(User, id=assigned_to_id)
        if not project.members.filter(id=assignee.id).exists():
            messages.error(request, "L'agent doit être membre du projet.")
            return

        created = apply_department_template(
            project,
            assignee,
            department=department or assignee.direction,
            actor=request.user,
        )
        if created:
            messages.success(request, f"{created} tâche(s) ajoutée(s) depuis le modèle département.")
        else:
            messages.info(request, "Toutes les tâches du modèle existent déjà pour cet agent.")
        return

    if action == 'smart_plan':
        project_id = request.POST.get('project_id', '').strip() or (str(default_project_id) if default_project_id else '')
        use_ai = request.POST.get('use_ai', '1').strip() != '0'
        if not project_id:
            messages.error(request, "Sélectionnez un projet pour la planification auto.")
            return

        project = get_object_or_404(Project, id=project_id)
        if not project.members.exists():
            messages.error(request, "Ajoutez d'abord des membres au projet.")
            return

        result = apply_smart_project_plan(project, actor=request.user, use_ai=use_ai)
        source = result.get('source')
        if result.get('created'):
            detail = f" ({'IA' if source == 'ai' else 'règles métier'})"
            messages.success(request, f"{result['message']}{detail}")
        else:
            hint = ''
            if use_ai and not ai_available():
                hint = " Astuce : définissez OPENAI_API_KEY pour activer l'IA (les règles restent actives)."
            messages.info(request, f"{result['message']}{hint}")
        return
        return

    messages.error(request, "Action non reconnue.")


# Create your views here.

@login_required(login_url='login')
@ensure_csrf_cookie
def dashboard(request):
    _ensure_work_session(request.user)
    is_management = request.user.is_superuser or request.user.role in ['admin', 'directeur']

    selected_task_project = request.GET.get('task_project', '').strip()
    personal_tasks = build_dashboard_tasks(
        request.user,
        project_id=selected_task_project or None,
    )
    open_tasks = personal_tasks['open_tasks']
    done_tasks = personal_tasks['done_tasks']
    profile_progress = personal_tasks['profile_progress']
    due_soon_tasks = get_due_soon_tasks(request.user)
    overdue_tasks = get_overdue_tasks(request.user)
    show_guide = not getattr(request.user, 'has_seen_guide', True)

    # Marquer les notifications comme lues après construction (le badge "Nouveau" reste visible cette fois)
    TaskAssignmentNotification.objects.filter(
        user=request.user,
        is_read=False,
    ).update(is_read=True)

    if is_management:
        projects_qs = Project.objects.select_related('manager').prefetch_related('members')
        project_status_counts = {
            'pending': projects_qs.filter(status='pending').count(),
            'progress': projects_qs.filter(status='progress').count(),
            'urgent': projects_qs.filter(status='urgent').count(),
            'awaiting_delivery': projects_qs.filter(status='awaiting_delivery').count(),
            'done': projects_qs.filter(status='done').count(),
        }
        total_projects = sum(project_status_counts.values())
        progress_ratio = round((project_status_counts['done'] / total_projects) * 100) if total_projects else 0

        tasks_qs = ProjectTask.objects.select_related('assigned_to', 'project')
        task_status_counts = {
            'pending': tasks_qs.filter(status='pending').count(),
            'in_progress': tasks_qs.filter(status='in_progress').count(),
            'done': tasks_qs.filter(status='done').count(),
        }
        total_tasks = sum(task_status_counts.values())
        task_completion_ratio = round((task_status_counts['done'] / total_tasks) * 100) if total_tasks else 0

        direction_labels = dict(TECH_BRANCH_CHOICES)
        department_stats = []
        for branch_value, branch_label in TECH_BRANCH_CHOICES:
            dept_tasks = tasks_qs.filter(department=branch_value)
            branch_projects = projects_qs.filter(branch=branch_value).count()
            dept_total = dept_tasks.count()
            department_stats.append({
                'label': branch_label,
                'value': branch_value,
                'projects': branch_projects,
                'pending': dept_tasks.filter(status='pending').count(),
                'in_progress': dept_tasks.filter(status='in_progress').count(),
                'done': dept_tasks.filter(status='done').count(),
                'total': dept_total,
            })

        worker_stats = []
        agents = User.objects.filter(role='agent').order_by('username')
        for agent in agents:
            agent_tasks = tasks_qs.filter(assigned_to=agent)
            agent_total = agent_tasks.count()
            if not agent_total:
                continue
            worker_stats.append({
                'user': agent,
                'direction': direction_labels.get(agent.direction, agent.direction),
                'pending': agent_tasks.filter(status='pending').count(),
                'in_progress': agent_tasks.filter(status='in_progress').count(),
                'done': agent_tasks.filter(status='done').count(),
                'total': agent_total,
                'progress': round((agent_tasks.filter(status='done').count() / agent_total) * 100),
            })

        active_tasks = tasks_qs.filter(status='in_progress').order_by('-updated_at')[:12]
        unfinished_tasks = tasks_qs.exclude(status='done').order_by('department', 'assigned_to__username', 'order')[:20]

        now = timezone.now()
        today = timezone.localdate()
        try:
            today_entries = AgentTimeEntry.objects.filter(user=request.user, started_at__date=today)
        except Exception:
            today_entries = AgentTimeEntry.objects.none()

        active_task_entry = _open_entry_for_user(request.user, 'task')
        open_pause_entry = _open_entry_for_user(request.user, 'pause')
        open_work_entry = _open_entry_for_user(request.user, 'work')
        task_elapsed_seconds = _entry_elapsed_seconds(active_task_entry, now) if active_task_entry else 0
        total_work_seconds = sum(
            _entry_elapsed_seconds(entry, now) if entry.ended_at is None else entry.duration_seconds
            for entry in today_entries.filter(entry_type='work')
        )
        total_pause_seconds = sum(
            _entry_elapsed_seconds(entry, now) if entry.ended_at is None else entry.duration_seconds
            for entry in today_entries.filter(entry_type='pause')
        )

        full_name = request.user.get_display_name()
        user_role_display = request.user.get_title_label()
        assigned_projects = Project.objects.filter(
            Q(members=request.user)
            | Q(manager=request.user)
            | Q(technical_director=request.user)
            | Q(commercial_agent=request.user)
        ).distinct().order_by('created_at', 'id')
        current_projects, current_project = _resolve_home_project_cards(
            request.user,
            [
                assigned_projects.filter(status='progress'),
                assigned_projects,
                projects_qs.filter(status='progress'),
                projects_qs.order_by('created_at', 'id'),
            ],
            empty_description='Vue d’ensemble direction — ouvrez les projets pour le détail.',
        )

        context = {
            'is_admin': request.user.is_superuser or request.user.role == 'admin',
            'is_management': True,
            'full_name': full_name,
            'user_role_display': user_role_display,
            'current_project': current_project,
            'current_projects': current_projects,
            'project_status_counts': project_status_counts,
            'total_projects': total_projects,
            'progress_ratio': progress_ratio,
            'recent_projects': projects_qs.order_by('-created_at', '-id')[:8],
            'task_status_counts': task_status_counts,
            'total_tasks': total_tasks,
            'task_completion_ratio': task_completion_ratio,
            'department_stats': department_stats,
            'worker_stats': worker_stats,
            'active_tasks': active_tasks,
            'unfinished_tasks': unfinished_tasks,
            'direction_labels': direction_labels,
            'tech_department_label': TECH_DEPARTMENT_LABEL,
            'branch_choices': TECH_BRANCH_CHOICES,
            'open_tasks': open_tasks,
            'done_tasks': done_tasks,
            'tasks': open_tasks,
            'profile_progress': profile_progress,
            'due_soon_tasks': due_soon_tasks,
            'overdue_tasks': overdue_tasks,
            'show_guide': show_guide,
            'task_project_choices': Project.objects.order_by('created_at', 'id')[:50],
            'selected_task_project': selected_task_project,
            'time_stats': [
                {'label': 'T. sur une tâche', 'value': _format_seconds(task_elapsed_seconds), 'highlight': True},
                {'label': 'Temps de travail', 'value': _format_seconds(total_work_seconds)},
                {'label': 'Temps de pause', 'value': _format_seconds(total_pause_seconds)},
            ],
            'timer_state': {
                'active_task_label': active_task_entry.task_label if active_task_entry else '',
                'active_task_started_at': active_task_entry.started_at.isoformat() if active_task_entry else '',
                'active_pause_started_at': open_pause_entry.started_at.isoformat() if open_pause_entry else '',
                'active_work_started_at': open_work_entry.started_at.isoformat() if open_work_entry else '',
                'is_pause_running': open_pause_entry is not None,
                'is_work_running': open_work_entry is not None,
            },
        }
        return render(request, "management_dashboard.html", context)

    projects = Project.objects.all()
    reports = DailyReport.objects.select_related('user').order_by('-date', '-created_at')[:5]

    unread_messages_count = Message.objects.filter(receiver=request.user, is_read=False).count()
    new_project_assignments = Project.objects.filter(members=request.user).count()

    full_name = request.user.get_display_name()
    user_first_letter = (request.user.first_name or request.user.username)[0].upper()
    user_role_display = request.user.get_title_label()

    assigned_projects = Project.objects.filter(members=request.user).order_by('created_at', 'id')
    current_projects, current_project = _resolve_home_project_cards(
        request.user,
        [
            assigned_projects.filter(status='progress'),
            assigned_projects,
        ],
        empty_title='Aucun projet assigné',
        empty_description='Aucune assignation active pour le moment.',
    )

    now = timezone.now()
    today = timezone.localdate()
    try:
        today_entries = AgentTimeEntry.objects.filter(user=request.user, started_at__date=today)
    except Exception:
        today_entries = AgentTimeEntry.objects.none()

    total_work_seconds = sum(
        _entry_elapsed_seconds(entry, now) if entry.ended_at is None else entry.duration_seconds
        for entry in today_entries.filter(entry_type='work')
    )
    total_pause_seconds = sum(
        _entry_elapsed_seconds(entry, now) if entry.ended_at is None else entry.duration_seconds
        for entry in today_entries.filter(entry_type='pause')
    )

    active_task_entry = _open_entry_for_user(request.user, 'task')
    task_elapsed_seconds = _entry_elapsed_seconds(active_task_entry, now) if active_task_entry else 0

    time_stats = [
        {'label': 'T. sur une tâche', 'value': _format_seconds(task_elapsed_seconds), 'highlight': True},
        {'label': 'Temps de travail', 'value': _format_seconds(total_work_seconds)},
        {'label': 'Temps de pause', 'value': _format_seconds(total_pause_seconds)},
    ]

    is_admin = request.user.is_superuser or request.user.role == 'admin'

    open_pause_entry = _open_entry_for_user(request.user, 'pause')
    open_work_entry = _open_entry_for_user(request.user, 'work')

    context = {
        "projects": projects,
        "reports": reports,
        "full_name": full_name,
        "user_first_letter": user_first_letter,
        "user_role_display": user_role_display,
        "profile_progress": profile_progress,
        "current_project": current_project,
        "current_projects": current_projects,
        "open_tasks": open_tasks,
        "done_tasks": done_tasks,
        "tasks": open_tasks,
        "time_stats": time_stats,
        "is_admin": is_admin,
        "unread_messages_count": unread_messages_count,
        "new_project_assignments": new_project_assignments,
        "due_soon_tasks": due_soon_tasks,
        "overdue_tasks": overdue_tasks,
        "show_guide": show_guide,
        "task_project_choices": assigned_projects,
        "selected_task_project": selected_task_project,
        "timer_state": {
            "active_task_label": active_task_entry.task_label if active_task_entry else "",
            "active_task_started_at": active_task_entry.started_at.isoformat() if active_task_entry else "",
            "active_pause_started_at": open_pause_entry.started_at.isoformat() if open_pause_entry else "",
            "active_work_started_at": open_work_entry.started_at.isoformat() if open_work_entry else "",
            "is_pause_running": open_pause_entry is not None,
            "is_work_running": open_work_entry is not None,
        },
        "task_labels": [task['label'] for task in open_tasks],
    }

    return render(request, "dashboard.html", context)


@login_required(login_url='login')
@require_POST
def start_task_timer(request):
    task_label = request.POST.get('task_label', '').strip()
    task_id = request.POST.get('task_id', '').strip()
    if not task_label and not task_id:
        return JsonResponse({'error': 'task_label ou task_id requis'}, status=400)

    project_task = get_task_for_user(request.user, task_id=task_id or None, task_label=task_label or None)
    if project_task:
        task_label = project_task.title
        ProjectTask.objects.filter(
            assigned_to=request.user,
            status='in_progress',
        ).exclude(id=project_task.id).update(status='pending')
        set_task_status(project_task, 'in_progress')
    elif not task_label:
        return JsonResponse({'error': 'Tâche introuvable'}, status=404)

    now = timezone.now()
    open_pause = _open_entry_for_user(request.user, 'pause')
    if open_pause:
        _close_entry(open_pause, now)

    open_task = _open_entry_for_user(request.user, 'task')
    if open_task and open_task.task_label != task_label:
        _close_entry(open_task, now)

    if not _open_entry_for_user(request.user, 'task'):
        AgentTimeEntry.objects.create(
            user=request.user,
            entry_type='task',
            task_label=task_label,
            started_at=now,
        )

    return JsonResponse({
        'ok': True,
        'task_label': task_label,
        'task_id': project_task.id if project_task else None,
        'status': project_task.status if project_task else 'in_progress',
    })


@login_required(login_url='login')
@require_POST
def complete_task_timer(request):
    task_label = request.POST.get('task_label', '').strip()
    task_id = request.POST.get('task_id', '').strip()
    now = timezone.now()

    project_task = get_task_for_user(request.user, task_id=task_id or None, task_label=task_label or None)

    open_task = _open_entry_for_user(request.user, 'task')
    if not open_task:
        if project_task and project_task.status != 'done':
            set_task_status(project_task, 'done')
        return JsonResponse({'ok': True, 'duration_seconds': 0, 'status': 'done'})

    if task_label and open_task.task_label != task_label:
        return JsonResponse({'error': 'Cette tâche n’est pas active'}, status=409)

    _close_entry(open_task, now)

    if project_task:
        set_task_status(project_task, 'done')

    return JsonResponse({
        'ok': True,
        'duration_seconds': open_task.duration_seconds,
        'status': 'done',
        'task_id': project_task.id if project_task else None,
    })


@login_required(login_url='login')
@require_POST
def toggle_pause_timer(request):
    now = timezone.now()
    open_pause = _open_entry_for_user(request.user, 'pause')

    if open_pause:
        _close_entry(open_pause, now)
        return JsonResponse({'ok': True, 'is_pause_running': False, 'duration_seconds': open_pause.duration_seconds})

    AgentTimeEntry.objects.create(
        user=request.user,
        entry_type='pause',
        started_at=now,
    )
    return JsonResponse({'ok': True, 'is_pause_running': True})


@login_required(login_url='login')
def projects_list(request):
    projects = accessible_projects(request.user).select_related(
        'manager', 'technical_director', 'commercial_agent'
    ).prefetch_related('members')

    status = request.GET.get('status', '').strip()
    branch = request.GET.get('branch', '').strip()
    if status:
        projects = projects.filter(status=status)
    if branch:
        projects = projects.filter(branch=normalize_branch(branch))

    is_manager = can_manage_projects(request.user)

    if request.method == 'POST':
        if not is_manager:
            return HttpResponseForbidden(
                "Seuls le Directeur Technique (Japhete Kuta) et l’Ass. Directeur Technique "
                "(Emmanuel Maki) peuvent créer, modifier ou terminer un projet."
            )

        action = request.POST.get('action', 'create').strip() or 'create'

        if action in {'complete', 'reopen', 'awaiting_delivery'}:
            project_id = request.POST.get('project_id', '').strip()
            project = get_object_or_404(Project, id=project_id)
            if action == 'complete':
                if request.POST.get('confirm_done') != '1':
                    messages.error(request, "Confirmez que le projet est bien terminé.")
                    return redirect('projects_list')
                project.status = 'done'
                project.show_on_home = False
                project.home_order = 0
                project.save(update_fields=['status', 'show_on_home', 'home_order'])
                messages.success(request, f'Projet « {project.name} » marqué comme terminé.')
            elif action == 'awaiting_delivery':
                project.status = 'awaiting_delivery'
                project.show_on_home = False
                project.home_order = 0
                project.save(update_fields=['status', 'show_on_home', 'home_order'])
                messages.success(
                    request,
                    f'Projet « {project.name} » passé en attente de livraison.',
                )
            else:
                project.status = 'progress'
                project.save(update_fields=['status'])
                messages.success(request, f'Projet « {project.name} » réouvert (en cours).')
            return redirect('projects_list')

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        start_date = request.POST.get('start_date', '').strip()
        end_date = request.POST.get('end_date', '').strip()
        project_status = request.POST.get('status', 'pending').strip() or 'pending'
        valid_project_statuses = {value for value, _ in Project.STATUS_CHOICES}
        if project_status not in valid_project_statuses:
            project_status = 'pending'
        if project_status == 'done' and request.POST.get('confirm_done') != '1':
            messages.error(request, "Confirmez que le projet est bien terminé avant d'enregistrer.")
            return redirect('projects_list')
        branch = normalize_branch(request.POST.get('branch', 'metal_design').strip())
        member_ids = request.POST.getlist('members')
        commercial_agent_id = request.POST.get('commercial_agent', '').strip()

        if action == 'update':
            project_id = request.POST.get('project_id', '').strip()
            project = get_object_or_404(Project, id=project_id)
            if not all([name, description, start_date, end_date]):
                messages.error(request, "Tous les champs du projet sont requis.")
                return redirect('projects_list')

            commercial_agent = User.objects.filter(id=commercial_agent_id).first() if commercial_agent_id else None
            if not commercial_agent:
                messages.error(request, "Veuillez choisir un agent commercial pour ce projet.")
                return redirect('projects_list')

            project.name = name
            project.description = description
            project.start_date = start_date
            project.end_date = end_date
            project.status = project_status
            project.branch = branch
            project.commercial_agent = commercial_agent

            if project_status == 'done':
                project.show_on_home = False
                project.home_order = 0

            cover = request.FILES.get('cover_image')
            if cover:
                cover_error = validate_image_upload(cover)
                if cover_error:
                    messages.error(request, cover_error)
                    return redirect('projects_list')
                if project.cover_image:
                    project.cover_image.delete(save=False)
                project.cover_image = cover

            if request.POST.get('remove_cover') == '1' and project.cover_image:
                project.cover_image.delete(save=False)
                project.cover_image = None

            project.save()

            if project_status != 'done':
                show_on_home, home_order = _parse_home_feature(request.POST)
                ok, feature_note = _apply_home_feature(project, show_on_home, home_order)
                if feature_note:
                    messages.info(request, feature_note)
            else:
                # Déjà retiré de l’Accueil ci-dessus
                pass

            members = list(User.objects.filter(id__in=member_ids)) if member_ids else []
            for stakeholder in (project.technical_director, project.manager, commercial_agent):
                if stakeholder and stakeholder not in members:
                    members.append(stakeholder)
            project.members.set(members)
            notify_commercial_on_project(project, actor=request.user, members=members)
            messages.success(request, "Projet mis à jour.")
            return redirect('projects_list')

        if not all([name, description, start_date, end_date]):
            messages.error(request, "Tous les champs du projet sont requis.")
            return redirect('projects_list')

        technical_director = _default_technical_director()
        manager = _default_project_manager() or request.user
        commercial_agent = User.objects.filter(id=commercial_agent_id).first() if commercial_agent_id else None

        if not commercial_agent:
            messages.error(request, "Veuillez choisir un agent commercial pour ce projet.")
            return redirect('projects_list')

        cover = request.FILES.get('cover_image')
        if cover:
            cover_error = validate_image_upload(cover)
            if cover_error:
                messages.error(request, cover_error)
                return redirect('projects_list')

        # À la création, on n’accepte pas "terminé" sans confirmation claire
        if project_status == 'done':
            project_status = 'pending'

        project = Project.objects.create(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            status=project_status,
            branch=branch,
            manager=manager,
            technical_director=technical_director,
            commercial_agent=commercial_agent,
            cover_image=cover if cover else None,
        )

        show_on_home, home_order = _parse_home_feature(request.POST)
        _ok, feature_note = _apply_home_feature(project, show_on_home, home_order)
        if feature_note:
            messages.info(request, feature_note)

        members = list(User.objects.filter(id__in=member_ids)) if member_ids else []
        for stakeholder in (technical_director, manager, commercial_agent):
            if stakeholder and stakeholder not in members:
                members.append(stakeholder)
        project.members.set(members)
        plan_result = ensure_project_tasks(project, actor=request.user, use_ai=True)
        notify_commercial_on_project(project, actor=request.user, members=members)

        created_n = (plan_result or {}).get('created') or 0
        source = (plan_result or {}).get('source') or 'rules'
        if created_n:
            via = 'IA' if source == 'ai' else 'règles métier'
            messages.success(
                request,
                f"Projet créé avec succès. {created_n} tâche(s) planifiée(s) automatiquement ({via}).",
            )
        else:
            messages.success(request, "Projet créé avec succès.")
        return redirect('projects_list')

    ProjectAssignmentNotification.objects.filter(
        user=request.user,
        is_read=False,
    ).update(is_read=True)

    # Séparer actifs / terminés pour l’affichage (sauf filtre statut explicite)
    if status == 'done':
        active_projects = Project.objects.none()
        completed_projects = projects
    elif status:
        active_projects = projects
        completed_projects = Project.objects.none()
    else:
        active_projects = projects.exclude(status='done')
        completed_projects = projects.filter(status='done')

    completed_by_month = _group_completed_projects_by_month(completed_projects)
    completed_total = sum(group['count'] for group in completed_by_month)

    context = {
        'projects': projects,
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'completed_by_month': completed_by_month,
        'completed_total': completed_total,
        'status_choices': Project.STATUS_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'tech_department_label': TECH_DEPARTMENT_LABEL,
        'selected_status': status,
        'selected_branch': branch,
        'can_create_project': is_manager,
        'available_users': User.objects.filter(role='agent').order_by('username'),
        'commercial_agents': _commercial_agents_qs(),
        'default_technical_director': _default_technical_director(),
        'default_project_manager': _default_project_manager(),
        'is_admin': request.user.is_superuser or request.user.role == 'admin',
        'is_management': request.user.is_superuser or request.user.role in ['admin', 'directeur'],
        'home_featured_max': HOME_FEATURED_MAX,
        'home_featured_count': Project.objects.filter(show_on_home=True).count(),
        'home_next_order': _next_free_home_order(),
    }
    return render(request, 'projects.html', context)


@login_required(login_url='login')
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related('manager', 'technical_director', 'commercial_agent').prefetch_related('members'),
        id=project_id,
    )

    is_manager_role = _is_management_user(request.user)
    if not can_access_project(request.user, project):
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à ce projet.")

    ProjectAssignmentNotification.objects.filter(
        user=request.user,
        project=project,
        is_read=False,
    ).update(is_read=True)

    if request.method == 'POST' and is_manager_role:
        _handle_task_management_post(request, default_project_id=project.id)
        return redirect('project_detail', project_id=project.id)

    ensure_project_tasks(project)

    project_tasks = ProjectTask.objects.filter(project=project).select_related('assigned_to').order_by('assigned_to__username', 'order')
    tasks_by_member = {}
    for task in project_tasks:
        member_key = task.assigned_to_id
        if member_key not in tasks_by_member:
            tasks_by_member[member_key] = {
                'member': task.assigned_to,
                'tasks': [],
                'pending': 0,
                'in_progress': 0,
                'done': 0,
            }
        tasks_by_member[member_key]['tasks'].append(task)
        tasks_by_member[member_key][task.status] += 1

    context = {
        'project': project,
        'is_admin': request.user.is_superuser or request.user.role == 'admin',
        'is_management': is_manager_role,
        'tasks_by_member': list(tasks_by_member.values()),
        'direction_labels': dict(TECH_BRANCH_CHOICES),
        'direction_choices': TECH_BRANCH_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'tech_department_label': TECH_DEPARTMENT_LABEL,
        'status_choices': ProjectTask.STATUS_CHOICES,
        'department_templates': DEPARTMENT_TASK_TEMPLATES,
        'project_members': _project_stakeholders(project),
    }
    return render(request, 'project_detail.html', context)


@login_required(login_url='login')
@management_required
def manage_tasks(request):
    if request.method == 'POST':
        _handle_task_management_post(request)
        redirect_params = request.GET.urlencode()
        if redirect_params:
            return redirect(f"{request.path}?{redirect_params}")
        return redirect('manage_tasks')

    today = timezone.localdate()
    # Ordre stable : projet (date d'ajout) → agent → séquence métier (order) → id
    tasks = ProjectTask.objects.select_related('project', 'assigned_to').order_by(
        'project__created_at',
        'project_id',
        'assigned_to__first_name',
        'assigned_to__username',
        'order',
        'id',
    )

    project_id = request.GET.get('project_id', '').strip()
    assigned_to_id = request.GET.get('assigned_to_id', '').strip()
    department = request.GET.get('department', '').strip()
    status = request.GET.get('status', '').strip()
    focus = request.GET.get('focus', 'open').strip() or 'open'

    if project_id:
        tasks = tasks.filter(project_id=project_id)
    if assigned_to_id:
        tasks = tasks.filter(assigned_to_id=assigned_to_id)
    if department:
        tasks = tasks.filter(department=department)
    if status:
        tasks = tasks.filter(status=status)
    elif focus == 'open':
        tasks = tasks.exclude(status='done')
    elif focus == 'overdue':
        tasks = tasks.exclude(status='done').filter(due_date__lt=today).order_by(
            'due_date',
            'project__created_at',
            'project_id',
            'order',
            'id',
        )
    elif focus == 'due_soon':
        tasks = tasks.exclude(status='done').filter(
            due_date__gte=today,
            due_date__lte=today + timedelta(days=3),
        ).order_by(
            'due_date',
            'project__created_at',
            'project_id',
            'order',
            'id',
        )

    base_qs = ProjectTask.objects.all()
    if project_id:
        base_qs = base_qs.filter(project_id=project_id)
    if assigned_to_id:
        base_qs = base_qs.filter(assigned_to_id=assigned_to_id)
    if department:
        base_qs = base_qs.filter(department=department)

    stats = {
        'pending': base_qs.filter(status='pending').count(),
        'in_progress': base_qs.filter(status='in_progress').count(),
        'done': base_qs.filter(status='done').count(),
        'overdue': base_qs.exclude(status='done').filter(due_date__lt=today).count(),
        'due_soon': base_qs.exclude(status='done').filter(
            due_date__gte=today,
            due_date__lte=today + timedelta(days=3),
        ).count(),
    }

    task_rows = []
    current_project_id = None
    for task in tasks[:120]:
        due_state = ''
        if task.due_date and task.status != 'done':
            if task.due_date < today:
                due_state = 'overdue'
            elif task.due_date <= today + timedelta(days=3):
                due_state = 'soon'
        show_project_header = task.project_id != current_project_id
        current_project_id = task.project_id
        task_rows.append({
            'task': task,
            'due_state': due_state,
            'show_project_header': show_project_header,
        })

    context = {
        'task_rows': task_rows,
        'tasks_count': len(task_rows),
        'stats': stats,
        'today': today,
        'focus': focus,
        'projects': Project.objects.select_related('manager').order_by('created_at', 'id'),
        'agents': User.objects.filter(role='agent').order_by('username'),
        'direction_choices': TECH_BRANCH_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'tech_department_label': TECH_DEPARTMENT_LABEL,
        'status_choices': ProjectTask.STATUS_CHOICES,
        'department_templates': DEPARTMENT_TASK_TEMPLATES,
        'selected_project_id': project_id,
        'selected_assigned_to_id': assigned_to_id,
        'selected_department': department,
        'selected_status': status,
        'is_admin': request.user.is_superuser or request.user.role == 'admin',
        'is_management': True,
        'ai_assignment_enabled': ai_available(),
    }
    return render(request, 'manage_tasks.html', context)


# ===== VUES ADMIN =====

@admin_required
def admin_dashboard(request):
    """Dashboard d'admin avec statistiques"""
    
    users_count = User.objects.count()
    projects_count = Project.objects.count()
    messages_count = Message.objects.count()
    reports_count = DailyReport.objects.count()
    
    # Statistiques par statut de projet
    projects_by_status = Project.objects.values('status').annotate(count=Count('id'))
    
    # Derniers messages
    recent_messages = Message.objects.select_related('sender', 'receiver').order_by('-created_at')[:10]
    
    # Derniers rapports
    recent_reports = DailyReport.objects.select_related('user').order_by('-created_at')[:10]
    
    context = {
        'users_count': users_count,
        'projects_count': projects_count,
        'messages_count': messages_count,
        'reports_count': reports_count,
        'projects_by_status': projects_by_status,
        'recent_messages': recent_messages,
        'recent_reports': recent_reports,
    }
    
    return render(request, 'admin/dashboard.html', context)


@admin_required
def admin_users(request):
    """Gestion des utilisateurs"""
    
    users = User.objects.all().order_by('-date_joined')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            admin_count = User.objects.filter(is_superuser=True).count()
            
            if action == 'delete':
                delete_confirm = request.POST.get('delete_confirm', '').strip().upper()
                if delete_confirm != 'SUPPRIMER':
                    messages.error(request, "Confirmation invalide. Tapez SUPPRIMER.")
                    return redirect('admin_users')
                if user.id == request.user.id:
                    messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
                    return redirect('admin_users')
                if user.is_superuser and admin_count <= 1:
                    messages.error(request, "Impossible de supprimer le dernier administrateur.")
                    return redirect('admin_users')
                deleted_username = user.username
                deleted_id = user.id
                user.delete()
                messages.success(request, "Utilisateur supprimé.")
                write_audit_log(
                    request.user,
                    'admin_user_delete',
                    path=request.path,
                    method='POST',
                    metadata={'target_user_id': deleted_id, 'username': deleted_username},
                )
            elif action == 'make_admin':
                user.is_superuser = True
                user.is_staff = True
                user.role = 'admin'
                user.save()
                messages.success(request, f"« {user.username} » promu administrateur.")
                write_audit_log(
                    request.user,
                    'admin_make_admin',
                    path=request.path,
                    method='POST',
                    metadata={'target_user_id': user.id, 'username': user.username},
                )
            elif action == 'remove_admin':
                if user.id == request.user.id:
                    messages.error(request, "Vous ne pouvez pas retirer vos propres droits admin.")
                    return redirect('admin_users')
                if user.is_superuser and admin_count <= 1:
                    messages.error(request, "Impossible de retirer le dernier administrateur.")
                    return redirect('admin_users')
                user.is_superuser = False
                user.is_staff = False
                if user.role == 'admin':
                    user.role = 'agent'
                user.save()
                messages.success(request, f"Droits admin retirés pour « {user.username} ».")
                write_audit_log(
                    request.user,
                    'admin_remove_admin',
                    path=request.path,
                    method='POST',
                    metadata={'target_user_id': user.id, 'username': user.username},
                )
        except User.DoesNotExist:
            messages.error(request, "Utilisateur introuvable.")
        
        return redirect('admin_users')
    
    context = {
        'users': users,
    }
    
    return render(request, 'admin/users.html', context)


@admin_required
def admin_create_user(request):
    """Créer un nouvel utilisateur"""
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        role = request.POST.get('role', 'agent')
        direction = request.POST.get('direction', 'design')
        is_admin = request.POST.get('is_admin') == 'on'
        
        errors = []
        
        # Validation
        if not username:
            errors.append('Le nom d\'utilisateur est requis')
        elif User.objects.filter(username=username).exists():
            errors.append('Ce nom d\'utilisateur existe déjà')
        
        if not email:
            errors.append('L\'email est requis')
        elif User.objects.filter(email=email).exists():
            errors.append('Cet email existe déjà')
        
        if not password:
            errors.append('Le mot de passe est requis')
        elif len(password) < 10:
            errors.append('Le mot de passe doit contenir au moins 10 caractères')
        else:
            try:
                pseudo_user = User(username=username, email=email, first_name=first_name, last_name=last_name)
                validate_password(password, pseudo_user)
            except ValidationError as exc:
                errors.extend(exc.messages)
        
        if password != password_confirm:
            errors.append('Les mots de passe ne correspondent pas')
        
        if not errors:
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                direction=direction,
            )
            
            if is_admin:
                user.is_superuser = True
                user.is_staff = True
                user.save()

            write_audit_log(
                request.user,
                'admin_user_create',
                path=request.path,
                method='POST',
                metadata={'username': username, 'role': role, 'is_admin': is_admin},
            )
            return redirect('admin_users')
        
        context = {
            'errors': errors,
            'form_data': request.POST,
            'role_choices': User.ROLE_CHOICES,
            'direction_choices': TECH_BRANCH_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'tech_department_label': TECH_DEPARTMENT_LABEL,
        }
    else:
        context = {
            'role_choices': User.ROLE_CHOICES,
            'direction_choices': TECH_BRANCH_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'tech_department_label': TECH_DEPARTMENT_LABEL,
        }
    
    return render(request, 'admin/create_user.html', context)


@admin_required
def admin_projects(request):
    """Gestion des projets"""
    
    projects = Project.objects.select_related('manager').prefetch_related('members').order_by('created_at', 'id')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        project_id = request.POST.get('project_id')
        
        try:
            project = Project.objects.get(id=project_id)
            
            if action == 'delete':
                delete_confirm = request.POST.get('delete_confirm', '').strip().upper()
                if delete_confirm != 'SUPPRIMER':
                    messages.error(request, "Confirmation invalide. Tapez SUPPRIMER.")
                    return redirect('admin_projects')
                project.delete()
            elif action == 'status':
                new_status = request.POST.get('status')
                project.status = new_status
                project.save()
        except Project.DoesNotExist:
            pass
        
        return redirect('admin_projects')
    
    context = {
        'projects': projects,
        'status_choices': Project.STATUS_CHOICES,
    }
    
    return render(request, 'admin/projects.html', context)


@admin_required
def admin_messages(request):
    """Vue des messages entre utilisateurs"""
    
    messages = Message.objects.select_related('sender', 'receiver').order_by('-created_at')
    
    # Filtre par utilisateur si fourni
    user_id = request.GET.get('user_id')
    if user_id:
        messages = messages.filter(Q(sender_id=user_id) | Q(receiver_id=user_id))
    
    users = User.objects.all().order_by('username')
    
    context = {
        'messages': messages,
        'users': users,
        'selected_user': user_id,
    }
    
    return render(request, 'admin/messages.html', context)


@admin_required
def admin_reports(request):
    """Vue des rapports quotidiens"""
    
    reports = DailyReport.objects.select_related('user').order_by('-created_at')
    
    # Filtre par utilisateur si fourni
    user_id = request.GET.get('user_id')
    if user_id:
        reports = reports.filter(user_id=user_id)
    
    users = User.objects.all().order_by('username')
    
    context = {
        'reports': reports,
        'users': users,
        'selected_user': user_id,
    }
    
    return render(request, 'admin/reports.html', context)


@admin_required
def admin_audit_logs(request):
    logs = AuditLog.objects.select_related('user').order_by('-created_at')
    action = request.GET.get('action', '').strip()
    if action:
        logs = logs.filter(action=action)

    context = {
        'logs': logs[:400],
        'actions': AuditLog.objects.values_list('action', flat=True).distinct().order_by('action'),
        'selected_action': action,
    }
    return render(request, 'admin/audit_logs.html', context)
