from django.urls import path

from . import views

urlpatterns = [
    path('', views.machines_list, name='machines_list'),
    path('<int:machine_id>/', views.machine_detail, name='machine_detail'),
]
