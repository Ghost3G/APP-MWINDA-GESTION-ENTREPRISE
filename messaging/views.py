from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db.models import Q
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Message

User = get_user_model()


def _is_management(user):
    return user.is_superuser or user.role in ['admin', 'directeur']


def _conversation_messages(user, other_user):
    return Message.objects.filter(
        Q(sender=user, receiver=other_user) |
        Q(sender=other_user, receiver=user)
    ).order_by('created_at')


def _serialize_message(msg, current_user):
    return {
        'id': msg.id,
        'sender_id': msg.sender.id,
        'content': msg.content,
        'created_at': msg.created_at.strftime('%d/%m %H:%M'),
        'time_short': msg.created_at.strftime('%H:%M'),
        'is_sent': msg.sender.id == current_user.id,
        'is_read': msg.is_read,
        'message_type': msg.message_type,
    }


def _last_message_preview(user, other_user):
    last = _conversation_messages(user, other_user).last()
    if not last:
        return 'Aucun message'
    if last.message_type == 'call':
        prefix = '📞 Appel'
    else:
        prefix = last.content[:40]
    return prefix + ('…' if last.message_type == 'text' and len(last.content) > 40 else '')


@login_required
@ensure_csrf_cookie
def csrf_token_view(request):
    """Renvoie un token CSRF frais pour les appels AJAX."""
    return JsonResponse({'ok': True, 'csrfToken': get_token(request)})


@login_required
@ensure_csrf_cookie
def messaging_view(request):
    users = User.objects.exclude(id=request.user.id).filter(is_active=True).order_by('first_name', 'username')
    initial_conversations = []

    for user in users:
        unread_count = Message.objects.filter(
            sender=user,
            receiver=request.user,
            is_read=False,
            message_type='text',
        ).count()
        initial_conversations.append({
            'id': user.id,
            'username': user.username,
            'name': user.get_labeled_name(),
            'short_name': user.get_display_name(),
            'title': user.get_title_label(),
            'email': user.email,
            'branch': user.get_org_group_display(),
            'department': user.get_org_group_display(),
            'role': user.get_role_display(),
            'phone': user.phone or '',
            'has_phone': bool(user.phone),
            'unread_count': unread_count,
            'last_message': _last_message_preview(request.user, user),
            'initial': user.get_avatar_initial(),
            'avatar_url': user.avatar_url,
        })

    initial_conversations.sort(key=lambda item: (-item['unread_count'], item['name'].lower()))

    if request.method == 'POST':
        receiver_id = request.POST.get('receiver')
        content = request.POST.get('content', '').strip()

        try:
            receiver = User.objects.get(id=receiver_id)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Utilisateur introuvable'}, status=404)

        if not content:
            return JsonResponse({'error': 'Le message ne peut pas être vide'}, status=400)

        msg = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            content=content,
            message_type='text',
        )
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'message': _serialize_message(msg, request.user)})
        return redirect('messaging')

    return render(request, 'messaging.html', {
        'users': users,
        'initial_conversations': initial_conversations,
        'is_management': _is_management(request.user),
    })


@login_required
def get_messages(request, user_id):
    other_user = get_object_or_404(User, id=user_id)

    messages = _conversation_messages(request.user, other_user)
    Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False,
    ).update(is_read=True)

    return JsonResponse({
        'messages': [_serialize_message(msg, request.user) for msg in messages],
        'contact': {
            'id': other_user.id,
            'name': other_user.get_labeled_name(),
            'short_name': other_user.get_display_name(),
            'title': other_user.get_title_label(),
            'username': other_user.username,
            'branch': other_user.get_org_group_display(),
            'role': other_user.get_role_display(),
            'phone': other_user.phone or '',
            'email': other_user.email,
            'initial': other_user.get_avatar_initial(),
            'avatar_url': other_user.avatar_url,
        },
    })


@login_required
@require_POST
def send_message_api(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Message vide'}, status=400)

    msg = Message.objects.create(
        sender=request.user,
        receiver=other_user,
        content=content,
        message_type='text',
    )
    return JsonResponse({'ok': True, 'message': _serialize_message(msg, request.user)})


@login_required
@require_POST
def initiate_call(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    now_label = timezone.localtime().strftime('%H:%M')

    Message.objects.create(
        sender=request.user,
        receiver=other_user,
        content=f"📞 Appel vers {other_user.get_labeled_name()} à {now_label}",
        message_type='call',
    )

    phone = (other_user.phone or '').strip()
    tel_url = f'tel:{phone.replace(" ", "")}' if phone else ''

    return JsonResponse({
        'ok': True,
        'phone': phone,
        'tel_url': tel_url,
        'contact_name': other_user.get_labeled_name(),
        'has_phone': bool(phone),
        'message': 'Appel enregistré dans la conversation.',
    })


@login_required
def get_unread_count(request):
    unread_count = Message.objects.filter(
        receiver=request.user,
        is_read=False,
        message_type='text',
    ).count()
    unread_conversations = Message.objects.filter(
        receiver=request.user,
        is_read=False,
    ).values('sender').distinct().count()

    return JsonResponse({
        'unread_count': unread_count,
        'unread_conversations': unread_conversations,
    })


@login_required
def get_conversations(request):
    users = User.objects.exclude(id=request.user.id).filter(is_active=True).order_by('first_name', 'username')
    conversations = []

    for user in users:
        unread_count = Message.objects.filter(
            sender=user,
            receiver=request.user,
            is_read=False,
            message_type='text',
        ).count()
        conversations.append({
            'id': user.id,
            'username': user.username,
            'name': user.get_labeled_name(),
            'short_name': user.get_display_name(),
            'title': user.get_title_label(),
            'email': user.email,
            'branch': user.get_org_group_display(),
            'department': user.get_org_group_display(),
            'role': user.get_role_display(),
            'phone': user.phone or '',
            'has_phone': bool(user.phone),
            'unread_count': unread_count,
            'last_message': _last_message_preview(request.user, user),
            'initial': user.get_avatar_initial(),
            'avatar_url': user.avatar_url,
        })

    conversations.sort(key=lambda item: (-item['unread_count'], item['name'].lower()))

    return JsonResponse({'conversations': conversations})
