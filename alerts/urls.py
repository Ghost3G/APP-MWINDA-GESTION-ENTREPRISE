from django.urls import path

from . import views

urlpatterns = [
    path('', views.alerts_center, name='alerts_center'),
]
