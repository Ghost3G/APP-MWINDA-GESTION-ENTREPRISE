from django.urls import path

from . import views

urlpatterns = [
    path('', views.stock_dashboard, name='stock_dashboard'),
]
