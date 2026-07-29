from django.contrib.auth import get_user_model

from .branches import TECH_BRANCH_CHOICES, normalize_branch, get_branch_label
from .models import Project, ProjectTask, TaskAssignmentNotification

User = get_user_model()

DEPARTMENT_TASK_TEMPLATES = {
    'metal_design': [
        'Réception du brief technique',
        'Étude faisabilité métal',
        'Découpe laser / plasma',
        'Pliage et soudure',
        'Préparation surface métal',
        'Peinture / traitement',
        'Contrôle qualité métal',
        'Assemblage structure',
        'Installation chantier',
        'Clôture Metal Design',
    ],
    'wood_design': [
        'Réception du brief bois',
        'Croquis et cotes bois',
        'Découpe bois / CNC',
        'Ponçage et préparation',
        'Assemblage bois',
        'Finition vernis / laque',
        'Contrôle qualité bois',
        'Emballage bois',
        'Livraison / pose',
        'Clôture Wood Design',
    ],
    'branding': [
        'Réception du brief branding',
        'Analyse identité visuelle',
        'Proposition créative',
        'Déclinaisons graphiques',
        'Validation client branding',
        'Préparation fichiers prod',
        'Contrôle cohérence marque',
        'Livraison assets',
        'Clôture Branding',
    ],
    'signaletique': [
        'Réception du brief signalétique',
        'Repérage et mesures site',
        'Conception panneaux',
        'Découpe supports',
        'Pose signalétique',
        'Tests visibilité',
        'Contrôle qualité pose',
        'Livraison signalétique',
        'Clôture Signalétique',
    ],
    'gravure': [
        'Réception du brief gravure',
        'Préparation fichier gravure',
        'Réglage machine gravure',
        'Tests gravure',
        'Production série gravure',
        'Contrôle profondeur / netteté',
        'Finitions gravure',
        'Clôture Gravure',
    ],
    'design_rd_innovation': [
        'Brief R&D et innovation',
        'Recherche matériaux / procédés',
        'Prototypage rapide',
        'Tests et itérations',
        'Validation prototype',
        'Documentation technique',
        'Transfert vers production',
        'Clôture Design RD & Innovation',
    ],
}

DEFAULT_TASK_TEMPLATES = DEPARTMENT_TASK_TEMPLATES['metal_design']


def get_templates_for_department(department):
    branch = normalize_branch(department)
    return DEPARTMENT_TASK_TEMPLATES.get(branch, DEFAULT_TASK_TEMPLATES)


def resolve_task_branch(project, user, department=None):
    if department:
        return normalize_branch(department)
    if getattr(project, 'branch', None):
        return normalize_branch(project.branch)
    return normalize_branch(getattr(user, 'direction', None))


def get_next_task_order(project, user):
    last_task = ProjectTask.objects.filter(project=project, assigned_to=user).order_by('-order').first()
    return (last_task.order + 1) if last_task else 0


def notify_task_assignment(task, actor=None, users=None):
    """Crée / réactive une notification in-app pour les destinataires d'une tâche."""
    recipients = []
    if users is not None:
        recipients = [user for user in users if user]
    elif task.assigned_to_id:
        recipients = [task.assigned_to]

    for user in recipients:
        if actor and getattr(actor, 'id', None) == user.id:
            continue
        notification, created = TaskAssignmentNotification.objects.get_or_create(
            user=user,
            task=task,
            defaults={'is_read': False},
        )
        if not created and notification.is_read:
            notification.is_read = False
            notification.save(update_fields=['is_read'])


def create_project_task(project, user, title, department=None, status='pending', notify=True, actor=None, due_date=None):
    branch = resolve_task_branch(project, user, department)
    task = ProjectTask.objects.create(
        project=project,
        assigned_to=user,
        title=title.strip(),
        department=branch,
        order=get_next_task_order(project, user),
        status=status,
        due_date=due_date or None,
    )
    if notify:
        notify_task_assignment(task, actor=actor)
    return task


def create_default_tasks_for_member(project, user):
    if ProjectTask.objects.filter(project=project, assigned_to=user).exists():
        return 0

    branch = resolve_task_branch(project, user)
    templates = get_templates_for_department(branch)
    for index, title in enumerate(templates):
        ProjectTask.objects.create(
            project=project,
            assigned_to=user,
            title=title,
            department=branch,
            order=index,
            status='pending',
        )
    return len(templates)


def apply_department_template(project, user, department=None, actor=None):
    branch = resolve_task_branch(project, user, department)
    templates = get_templates_for_department(branch)
    existing_titles = set(
        ProjectTask.objects.filter(project=project, assigned_to=user).values_list('title', flat=True)
    )
    created = 0
    for title in templates:
        if title in existing_titles:
            continue
        create_project_task(project, user, title, department=branch, actor=actor)
        created += 1
    return created


def ensure_project_tasks(project):
    for member in project.members.all():
        create_default_tasks_for_member(project, member)


def ensure_user_has_tasks(user):
    assigned_projects = Project.objects.filter(members=user).order_by('created_at', 'id')
    for project in assigned_projects:
        create_default_tasks_for_member(project, user)


def get_task_for_user(user, task_id=None, task_label=None):
    queryset = ProjectTask.objects.filter(assigned_to=user)
    if task_id:
        return queryset.filter(id=task_id).first()
    if task_label:
        return queryset.filter(
            title=task_label,
            status__in=['pending', 'in_progress'],
        ).order_by('-updated_at').first()
    return None


def set_task_status(task, status):
    from django.utils import timezone

    task.status = status
    if status == 'in_progress' and not task.started_at:
        task.started_at = timezone.now()
    if status == 'done':
        task.completed_at = timezone.now()
    task.save(update_fields=['status', 'started_at', 'completed_at', 'updated_at'])


def update_project_task(task, *, title=None, assigned_to=None, department=None, status=None, due_date=None, actor=None):
    from django.utils import timezone

    previous_assignee_id = task.assigned_to_id
    if title is not None:
        task.title = title.strip()
    if assigned_to is not None:
        task.assigned_to = assigned_to
    if department is not None:
        task.department = normalize_branch(department)
    if due_date is not None:
        task.due_date = due_date or None
    if status is not None:
        task.status = status
        if status == 'in_progress' and not task.started_at:
            task.started_at = timezone.now()
        if status == 'done':
            task.completed_at = timezone.now()
    task.save()
    if assigned_to is not None and assigned_to.id != previous_assignee_id:
        notify_task_assignment(task, actor=actor)
    return task


def build_dashboard_tasks(user, project=None, project_id=None):
    """Retourne les tâches personnelles : en cours + terminées (tous projets)."""
    ensure_user_has_tasks(user)

    queryset = ProjectTask.objects.filter(assigned_to=user).select_related('project')
    if project_id:
        queryset = queryset.filter(project_id=project_id)
    elif project:
        queryset = queryset.filter(project=project)
    queryset = queryset.order_by('-updated_at', 'order')

    open_tasks = []
    done_tasks = []
    for task in queryset:
        item = {
            'id': task.id,
            'label': task.title,
            'status': task.status,
            'active': task.status == 'in_progress',
            'visible': True,
            'project_name': task.project.name,
            'project_id': task.project_id,
            'is_new': False,
        }
        if task.status == 'done':
            done_tasks.append(item)
        else:
            open_tasks.append(item)

    # Marquer les tâches avec notification non lue
    unread_ids = set(
        TaskAssignmentNotification.objects.filter(
            user=user,
            is_read=False,
            task_id__in=[item['id'] for item in open_tasks],
        ).values_list('task_id', flat=True)
    )
    for item in open_tasks:
        item['is_new'] = item['id'] in unread_ids

    # Prioriser les nouvelles + en cours
    open_tasks.sort(key=lambda t: (0 if t['is_new'] else 1, 0 if t['active'] else 1, t['label']))

    total = len(open_tasks) + len(done_tasks)
    done_count = len(done_tasks)
    profile_progress = round((done_count / total) * 100) if total else 0

    return {
        'open_tasks': open_tasks,
        'done_tasks': done_tasks,
        'all_tasks': open_tasks + done_tasks,
        'profile_progress': profile_progress,
    }
