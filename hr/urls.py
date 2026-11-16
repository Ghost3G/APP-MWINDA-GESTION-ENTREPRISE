from django.urls import path

from .views import hr_dashboard, hr_documents, hr_leaves, hr_staff

urlpatterns = [
    path('', hr_dashboard, name='hr_dashboard'),
    path('effectif/', hr_staff, name='hr_staff'),
    path('conges/', hr_leaves, name='hr_leaves'),
    path('documents/', hr_documents, name='hr_documents'),
]
