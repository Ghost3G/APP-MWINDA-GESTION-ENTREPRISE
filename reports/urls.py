from django.urls import path

from .views import (
    reports_list,
    finance_dashboard,
    finance_clients,
    report_pdf,
    report_a4_view,
    finance_pdf,
    finance_a4_view,
    finance_export_excel,
    crm_reports_list,
    crm_report_detail,
    crm_report_pdf,
)
from .crm_views import (
    crm_my_clients,
    crm_relance_prospect,
    crm_relance_recouvrement,
    crm_new_client,
    crm_reassign,
)

urlpatterns = [
    path('', reports_list, name='reports_list'),
    path('<int:report_id>/pdf/', report_pdf, name='report_pdf'),
    path('<int:report_id>/a4/', report_a4_view, name='report_a4'),
    path('finance/', finance_dashboard, name='finance_dashboard'),
    path('finance/clients/', finance_clients, name='finance_clients'),
    path('crm/', crm_my_clients, name='crm_my_clients'),
    path('crm/mes-clients/', crm_my_clients, name='crm_portfolio'),
    path('crm/relance/prospect/', crm_relance_prospect, name='crm_relance_prospect'),
    path('crm/relance/recouvrement/', crm_relance_recouvrement, name='crm_relance_recouvrement'),
    path('crm/nouveau-client/', crm_new_client, name='crm_new_client'),
    path('crm/affecter/', crm_reassign, name='crm_reassign'),
    path('crm/reports/', crm_reports_list, name='crm_reports_list'),
    path('crm/reports/<int:report_id>/', crm_report_detail, name='crm_report_detail'),
    path('crm/reports/<int:report_id>/pdf/', crm_report_pdf, name='crm_report_pdf'),
    path('finance/pdf/<str:period>/', finance_pdf, name='finance_pdf'),
    path('finance/a4/<str:period>/', finance_a4_view, name='finance_a4'),
    path('finance/export/<str:period>/', finance_export_excel, name='finance_export'),
]
