from django.urls import path

from .views import (
    users_directory,
    presence_dashboard,
    presence_pdf,
    presence_a4_view,
    overtime_dashboard,
    overtime_export_pdf,
    overtime_export_csv,
)

urlpatterns = [
    path('', users_directory, name='users_list'),
    path('presence/', presence_dashboard, name='presence_dashboard'),
    path('presence/overtime/', overtime_dashboard, name='overtime_dashboard'),
    path('presence/overtime/export/pdf/', overtime_export_pdf, name='overtime_export_pdf'),
    path('presence/overtime/export/csv/', overtime_export_csv, name='overtime_export_csv'),
    path('presence/<int:agent_id>/pdf/', presence_pdf, name='presence_pdf'),
    path('presence/<int:agent_id>/a4/', presence_a4_view, name='presence_a4'),
]
