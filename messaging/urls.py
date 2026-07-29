from django.urls import path
from .views import (
    messaging_view,
    get_messages,
    get_unread_count,
    get_conversations,
    send_message_api,
    initiate_call,
    csrf_token_view,
)

urlpatterns = [
    path('', messaging_view, name='messaging'),
    path('api/csrf/', csrf_token_view, name='messaging_csrf'),
    path('api/messages/<int:user_id>/', get_messages, name='get_messages'),
    path('api/messages/<int:user_id>/send/', send_message_api, name='send_message_api'),
    path('api/call/<int:user_id>/', initiate_call, name='initiate_call'),
    path('api/unread-count/', get_unread_count, name='get_unread_count'),
    path('api/conversations/', get_conversations, name='get_conversations'),
]
