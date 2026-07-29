from django.urls import path

from .views import projects_list, project_detail, start_task_timer, complete_task_timer, toggle_pause_timer
from .board_views import (
    task_board,
    board_task_detail,
    board_update_status,
    board_update_task,
    board_add_comment,
    board_add_checklist,
    board_add_checklist_item,
    board_toggle_checklist_item,
    board_upload_attachment,
    board_create_task,
)

urlpatterns = [
    path('', projects_list, name='projects_list'),
    path('board/', task_board, name='task_board'),
    path('<int:project_id>/', project_detail, name='project_detail'),
    path('api/timer/start-task/', start_task_timer, name='start_task_timer'),
    path('api/timer/complete-task/', complete_task_timer, name='complete_task_timer'),
    path('api/timer/toggle-pause/', toggle_pause_timer, name='toggle_pause_timer'),
    path('api/board/tasks/create/', board_create_task, name='board_create_task'),
    path('api/board/tasks/<int:task_id>/', board_task_detail, name='board_task_detail'),
    path('api/board/tasks/<int:task_id>/status/', board_update_status, name='board_update_status'),
    path('api/board/tasks/<int:task_id>/update/', board_update_task, name='board_update_task'),
    path('api/board/tasks/<int:task_id>/comments/', board_add_comment, name='board_add_comment'),
    path('api/board/tasks/<int:task_id>/checklists/', board_add_checklist, name='board_add_checklist'),
    path('api/board/checklists/<int:checklist_id>/items/', board_add_checklist_item, name='board_add_checklist_item'),
    path('api/board/checklist-items/<int:item_id>/toggle/', board_toggle_checklist_item, name='board_toggle_checklist_item'),
    path('api/board/tasks/<int:task_id>/attachments/', board_upload_attachment, name='board_upload_attachment'),
]
