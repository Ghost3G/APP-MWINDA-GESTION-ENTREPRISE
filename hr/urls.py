from django.urls import path

from .phase2_views import hr_recruitment, hr_reviews, hr_sanctions, hr_trainings
from .views import hr_dashboard, hr_documents, hr_leaves, hr_staff

urlpatterns = [
    path('', hr_dashboard, name='hr_dashboard'),
    path('effectif/', hr_staff, name='hr_staff'),
    path('conges/', hr_leaves, name='hr_leaves'),
    path('documents/', hr_documents, name='hr_documents'),
    path('recrutement/', hr_recruitment, name='hr_recruitment'),
    path('evaluations/', hr_reviews, name='hr_reviews'),
    path('formations/', hr_trainings, name='hr_trainings'),
    path('sanctions/', hr_sanctions, name='hr_sanctions'),
]
