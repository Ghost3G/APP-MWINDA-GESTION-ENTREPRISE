from django.urls import path

from .views import users_directory, presence_dashboard, presence_pdf, presence_a4_view

urlpatterns = [
    path('', users_directory, name='users_list'),
    path('presence/', presence_dashboard, name='presence_dashboard'),
    path('presence/<int:agent_id>/pdf/', presence_pdf, name='presence_pdf'),
    path('presence/<int:agent_id>/a4/', presence_a4_view, name='presence_a4'),
]
