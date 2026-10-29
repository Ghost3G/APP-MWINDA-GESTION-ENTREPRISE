from django.urls import path

from . import views

urlpatterns = [
    path('', views.stock_dashboard, name='stock_dashboard'),
    path('fournisseurs/', views.stock_suppliers, name='stock_suppliers'),
    path('logistique/', views.stock_logistics, name='stock_logistics'),
]
