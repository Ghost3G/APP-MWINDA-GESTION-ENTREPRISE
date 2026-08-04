"""Notifications unifiées + endpoints associés."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from messaging.models import Message
from projects.models import ProjectAssignmentNotification, ProjectTask, TaskAssignmentNotification
from users.permissions import is_commercial_lead


def build_notification_feed(user, limit=30):
    """Construit un fil unique : tâches, projets, messages."""
    items = []

    for notif in TaskAssignmentNotification.objects.filter(user=user).select_related(
        'task', 'task__project'
    )[:limit]:
        items.append({
            'id': f'task-{notif.id}',
            'kind': 'task',
            'title': 'Nouvelle tâche',
            'body': f'{notif.task.title} — {notif.task.project.name}',
            'url': '/',
            'is_read': notif.is_read,
            'created_at': notif.created_at,
        })

    for notif in ProjectAssignmentNotification.objects.filter(user=user).select_related(
        'project', 'project__commercial_agent'
    )[:limit]:
        if is_commercial_lead(user) and notif.project.commercial_agent_id:
            agent = notif.project.commercial_agent
            agent_label = agent.get_labeled_name() if agent else 'Commercial'
            title = 'Commercial affecté'
            body = f'{notif.project.name} — {agent_label}'
        else:
            title = 'Nouveau projet'
            body = notif.project.name
        items.append({
            'id': f'project-{notif.id}',
            'kind': 'project',
            'title': title,
            'body': body,
            'url': f'/projects/{notif.project_id}/',
            'is_read': notif.is_read,
            'created_at': notif.created_at,
        })

    for msg in Message.objects.filter(receiver=user).select_related('sender').order_by('-created_at')[:limit]:
        preview = 'Appel' if msg.message_type == 'call' else (msg.content[:80] or 'Message')
        items.append({
            'id': f'message-{msg.id}',
            'kind': 'message',
            'title': f'Message de {msg.sender.get_labeled_name()}',
            'body': preview,
            'url': f'/messaging/?user={msg.sender_id}',
            'is_read': msg.is_read,
            'created_at': msg.created_at,
        })

    items.sort(key=lambda item: item['created_at'], reverse=True)
    return items[:limit]


def get_due_soon_tasks(user, days=3):
    today = timezone.localdate()
    until = today + timedelta(days=days)
    return list(
        ProjectTask.objects.filter(
            assigned_to=user,
        ).exclude(status='done').exclude(due_date__isnull=True).filter(
            due_date__gte=today,
            due_date__lte=until,
        ).select_related('project').order_by('due_date')[:8]
    )


def get_overdue_tasks(user):
    today = timezone.localdate()
    return list(
        ProjectTask.objects.filter(
            assigned_to=user,
            due_date__lt=today,
        ).exclude(status='done').select_related('project').order_by('due_date')[:8]
    )


@login_required(login_url='login')
def notifications_feed(request):
    feed = build_notification_feed(request.user)
    payload = []
    for item in feed:
        payload.append({
            **item,
            'created_at': item['created_at'].strftime('%d/%m %H:%M'),
            'created_iso': item['created_at'].isoformat(),
        })
    unread = sum(1 for item in payload if not item['is_read'])
    return JsonResponse({'ok': True, 'items': payload, 'unread': unread})


@login_required(login_url='login')
@require_POST
def notifications_mark_read(request):
    TaskAssignmentNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    ProjectAssignmentNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    Message.objects.filter(receiver=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required(login_url='login')
@require_POST
def dismiss_onboarding(request):
    user = request.user
    if hasattr(user, 'has_seen_guide'):
        user.has_seen_guide = True
        user.save(update_fields=['has_seen_guide'])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('dashboard')
