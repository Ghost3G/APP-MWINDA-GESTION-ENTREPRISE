from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from projects.branches import TECH_BRANCH_CHOICES

# Create your models here.

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('directeur', 'Directeur'),
        ('agent', 'Agent'),
    )
    DEPARTMENT_CHOICES = (
        ('direction', 'Directeurs'),
        ('technique', 'Technique'),
        ('finance', 'Finance'),
        ('commercial', 'Commercial'),
        ('logistique', 'Logistique'),
        ('design_communication', 'Design et Communication'),
        ('rd', 'Recherche et Développement'),
    )
    ORG_GROUP_CHOICES = DEPARTMENT_CHOICES

    # Branche au sein du département technique
    DIRECTION_CHOICES = TECH_BRANCH_CHOICES
    BRANCH_CHOICES = TECH_BRANCH_CHOICES

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    org_group = models.CharField(
        'département',
        max_length=40,
        choices=DEPARTMENT_CHOICES,
        default='technique',
    )
    direction = models.CharField(max_length=50, choices=TECH_BRANCH_CHOICES, default='metal_design')
    job_title = models.CharField(max_length=180, blank=True)
    grade = models.CharField(max_length=80, blank=True)
    department_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    has_seen_guide = models.BooleanField(default=False)

    def get_display_name(self):
        full_name = self.get_full_name().strip()
        return full_name or self.username

    def get_title_label(self):
        """Titre métier affiché à côté du nom (Directeur Technique, Agent Commercial…)."""
        raw = (self.job_title or self.grade or '').strip()
        if raw:
            if raw.isupper() and len(raw) > 2:
                titled = raw.replace('_', ' ').title()
                # Petites particules en minuscules
                for particle in (' Et ', ' De ', ' Du ', ' Des ', ' La ', ' Le ', ' Les '):
                    titled = titled.replace(particle, particle.lower())
                return titled
            return raw

        if self.role == 'admin':
            return 'Administrateur'

        if self.role == 'directeur':
            director_titles = {
                'technique': 'Directeur Technique',
                'commercial': 'Directeur Commercial',
                'finance': 'Directeur Finance',
                'logistique': 'Directeur Logistique',
                'design_communication': 'Directeur Design',
                'rd': 'Directeur R&D',
                'direction': 'Directeur',
            }
            return director_titles.get(self.org_group, 'Directeur')

        org_titles = {
            'commercial': 'Agent Commercial',
            'finance': 'Agent Finance',
            'logistique': 'Agent Logistique',
            'design_communication': 'Agent Design',
            'rd': 'Agent R&D',
            'technique': 'Agent Technique',
            'direction': 'Direction',
        }
        return org_titles.get(self.org_group, 'Agent')

    def get_labeled_name(self):
        """Ex: Japhete Kuta / Directeur Technique"""
        name = self.get_display_name()
        title = self.get_title_label()
        if not title:
            return name
        return f'{name} / {title}'

    def get_avatar_initial(self):
        if self.first_name:
            return self.first_name[0].upper()
        return self.username[0].upper()

    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return ''

    # Fix reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )


class LoginAttempt(models.Model):
    username = models.CharField(max_length=150)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    attempted_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=False)

    class Meta:
        ordering = ('-attempted_at',)


class AuditLog(models.Model):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=120)
    path = models.CharField(max_length=300, blank=True)
    method = models.CharField(max_length=10, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ('-created_at',)