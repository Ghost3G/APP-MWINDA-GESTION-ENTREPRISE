from django.db import models
from django.conf import settings

from .branches import TECH_BRANCH_CHOICES, get_branch_label, normalize_branch

# Create your models here.

class Project(models.Model):

    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('progress', 'En cours'),
        ('urgent', 'Urgence'),
        ('done', 'Terminé'),
    )

    name = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    branch = models.CharField(
        max_length=50,
        choices=TECH_BRANCH_CHOICES,
        default='metal_design',
    )

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_projects'
    )

    technical_director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='technical_director_projects',
        blank=True,
        null=True,
    )

    commercial_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='commercial_projects',
        blank=True,
        null=True,
    )

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='projects'
    )

    cover_image = models.ImageField(
        upload_to='project_covers/',
        blank=True,
        null=True,
        verbose_name='Photo du projet',
    )

    # Accueil : jusqu'à 3 projets mis en avant (contrôle directeur)
    show_on_home = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Afficher sur l’Accueil',
    )
    home_order = models.PositiveSmallIntegerField(
        default=0,
        help_text='Position sur l’Accueil (1 à 3). 0 = non affiché.',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('created_at', 'id')

    def __str__(self):
        return self.name

    @property
    def cover_url(self):
        try:
            if not self.cover_image:
                return ''
            name = (getattr(self.cover_image, 'name', None) or '').strip()
            if not name:
                return ''
            if name.startswith('http://') or name.startswith('https://'):
                return name
            try:
                import cloudinary
                import os
                from django.conf import settings
                if getattr(settings, 'CLOUDINARY_STORAGE', None) or os.environ.get('CLOUDINARY_URL'):
                    return cloudinary.CloudinaryResource(
                        name,
                        resource_type='image',
                    ).build_url(secure=True)
            except Exception:
                pass
            return self.cover_image.url
        except Exception:
            return ''

    def get_branch_display_label(self):
        return get_branch_label(self.branch)

    def get_stakeholders(self):
        users = list(self.members.all())
        for user in (self.manager, self.technical_director, self.commercial_agent):
            if user and user not in users:
                users.insert(0, user)
        return users


class AgentTimeEntry(models.Model):
    ENTRY_TYPE_CHOICES = (
        ('work', 'Travail'),
        ('pause', 'Pause'),
        ('task', 'Tâche'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    task_label = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-started_at',)

    def __str__(self):
        suffix = f" - {self.task_label}" if self.task_label else ""
        return f"{self.user.username} | {self.entry_type}{suffix}"


class ProjectAssignmentNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_assignment_notifications',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='assignment_notifications',
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'project')
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.user.username} assigned to {self.project.name}"


class TaskAssignmentNotification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_assignment_notifications',
    )
    task = models.ForeignKey(
        'ProjectTask',
        on_delete=models.CASCADE,
        related_name='assignment_notifications',
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'task')
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.user.username} assigned to task {self.task_id}"


class ProjectTask(models.Model):
    STATUS_CHOICES = (
        ('pending', 'À faire'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_tasks',
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='task_collaborations',
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    department = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    labels = models.ManyToManyField('TaskLabel', blank=True, related_name='tasks')

    class Meta:
        ordering = ('project_id', 'order', 'id')
        indexes = [
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['department', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()}) - {self.assigned_to.username}"

    def get_department_display_label(self):
        return get_branch_label(self.department)

    def all_members(self):
        member_ids = set(self.members.values_list('id', flat=True))
        member_ids.add(self.assigned_to_id)
        return member_ids


class TaskLabel(models.Model):
    name = models.CharField(max_length=40, unique=True)
    color = models.CharField(max_length=7, default='#fde047')

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class TaskComment(models.Model):
    task = models.ForeignKey(ProjectTask, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)

    def __str__(self):
        return f"Commentaire sur {self.task.title} par {self.author.username}"


class TaskChecklist(models.Model):
    task = models.ForeignKey(ProjectTask, on_delete=models.CASCADE, related_name='checklists')
    title = models.CharField(max_length=120, default='Liste de contrôle')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('order', 'id')

    def __str__(self):
        return self.title


class TaskChecklistItem(models.Model):
    checklist = models.ForeignKey(TaskChecklist, on_delete=models.CASCADE, related_name='items')
    text = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('order', 'id')

    def __str__(self):
        return self.text


class TaskAttachment(models.Model):
    task = models.ForeignKey(ProjectTask, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to='task_attachments/%Y/%m/')
    original_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.original_name or self.file.name
