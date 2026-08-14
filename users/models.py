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
    COMPETENCY_PROFILE_CHOICES = (
        ('auto', 'Auto (déduit du profil)'),
        ('commercial', 'Commercial'),
        ('finance', 'Finance'),
        ('logistique', 'Logistique'),
        ('metal_design', 'Metal Design'),
        ('wood_design', 'Wood Design'),
        ('branding', 'Design Graphique / Branding'),
        ('signaletique', 'Signalétique'),
        ('gravure', 'Gravure'),
        ('design_rd_innovation', 'R&D / Innovation'),
    )

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
    phone = models.CharField(max_length=40, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    has_seen_guide = models.BooleanField(default=False)
    competency_profile = models.CharField(
        max_length=40,
        choices=COMPETENCY_PROFILE_CHOICES,
        default='auto',
    )

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
        """URL d’avatar fiable (Cloudinary public_id ou stockage local)."""
        try:
            if not self.avatar:
                return ''
            name = (getattr(self.avatar, 'name', None) or str(self.avatar) or '').strip()
            if not name:
                return ''
            if name.startswith('http://') or name.startswith('https://'):
                return name

            # Upload Cloudinary direct → public_id du type "avatars/user_12"
            try:
                import cloudinary
                from django.conf import settings
                if getattr(settings, 'CLOUDINARY_STORAGE', None) or __import__('os').environ.get('CLOUDINARY_URL'):
                    return cloudinary.CloudinaryResource(
                        name,
                        resource_type='image',
                    ).build_url(secure=True)
            except Exception:
                pass

            return self.avatar.url
        except Exception:
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


class OvertimeDayEntry(models.Model):
    """Journée(s) d'heures supplémentaires comptabilisées (saisie manuelle DT ou validation auto)."""

    SOURCE_CHOICES = (
        ('manual', 'Saisie manuelle'),
        ('auto_validated', 'Validé depuis connexion'),
    )

    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='overtime_entries',
        verbose_name='Agent',
    )
    work_date = models.DateField(db_index=True, verbose_name='Date prestée')
    days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Nombre de jours',
        help_text='Ex. 1 = journée entière, 0.5 = demi-journée.',
    )
    notes = models.CharField(max_length=500, blank=True, verbose_name='Motif / notes')
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='manual',
        verbose_name='Origine',
    )
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='overtime_entries_created',
        verbose_name='Saisi par',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-work_date', '-id')
        verbose_name = 'Jour supplémentaire'
        verbose_name_plural = 'Jours supplémentaires'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'work_date'),
                name='unique_overtime_user_date',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} · {self.work_date} · {self.days} j'