from django.urls import path

from .views import reports_list, finance_dashboard, report_pdf, report_a4_view

urlpatterns = [
    path('', reports_list, name='reports_list'),
    path('<int:report_id>/pdf/', report_pdf, name='report_pdf'),
    path('<int:report_id>/a4/', report_a4_view, name='report_a4'),
    path('finance/', finance_dashboard, name='finance_dashboard'),
]
