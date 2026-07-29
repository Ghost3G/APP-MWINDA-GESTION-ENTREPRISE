from django.urls import path

from .views import reports_list, finance_dashboard

urlpatterns = [
    path('', reports_list, name='reports_list'),
    path('finance/', finance_dashboard, name='finance_dashboard'),
]
