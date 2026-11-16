from django.conf import settings
from django.db import models
from django.utils import timezone


class LeaveRequest(models.Model):
    TYPE_ANNUAL = 'annual'
    TYPE_SICK = 'sick'
    TYPE_UNPAID = 'unpaid'
    TYPE_OTHER = 'other'
    TYPE_CHOICES = (
        (TYPE_ANNUAL, 'Congé annuel'),
        (TYPE_SICK, 'Maladie'),
        (TYPE_UNPAID, 'Sans solde'),
        (TYPE_OTHER, 'Autre'),
    )

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_PENDING, 'En attente'),
        (STATUS_APPROVED, 'Approuvé'),
        (STATUS_REJECTED, 'Refusé'),
        (STATUS_CANCELLED, 'Annulé'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests',
    )
    leave_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ANNUAL)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leave_reviews',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user_id} {self.leave_type} {self.start_date}→{self.end_date}'

    @property
    def days_count(self):
        if not self.start_date or not self.end_date:
            return 0
        return max((self.end_date - self.start_date).days + 1, 0)

    def mark_reviewed(self, reviewer, status, note=''):
        self.status = status
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = (note or '')[:255]
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])


class HRDocument(models.Model):
    KIND_CONTRACT = 'contract'
    KIND_ID = 'id_card'
    KIND_CV = 'cv'
    KIND_CERTIFICATE = 'certificate'
    KIND_OTHER = 'other'
    KIND_CHOICES = (
        (KIND_CONTRACT, 'Contrat'),
        (KIND_ID, 'Pièce d’identité'),
        (KIND_CV, 'CV'),
        (KIND_CERTIFICATE, 'Attestation / certificat'),
        (KIND_OTHER, 'Autre'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='hr_documents',
    )
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_OTHER)
    file = models.FileField(upload_to='hr_documents/%Y/%m/')
    notes = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hr_documents_uploaded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title


class JobApplication(models.Model):
    """Recrutement — candidatures."""
    STATUS_RECEIVED = 'received'
    STATUS_SCREENING = 'screening'
    STATUS_INTERVIEW = 'interview'
    STATUS_OFFER = 'offer'
    STATUS_HIRED = 'hired'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = (
        (STATUS_RECEIVED, 'Reçue'),
        (STATUS_SCREENING, 'Présélection'),
        (STATUS_INTERVIEW, 'Entretien'),
        (STATUS_OFFER, 'Offre'),
        (STATUS_HIRED, 'Embauché'),
        (STATUS_REJECTED, 'Refusée'),
    )

    full_name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    position = models.CharField(max_length=180)
    department = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    source = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    cv_file = models.FileField(upload_to='hr_recruitment/%Y/%m/', blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_applications_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.full_name} — {self.position}'


class PerformanceReview(models.Model):
    """Évaluations / entretiens."""
    RATING_CHOICES = (
        (1, 'Insuffisant'),
        (2, 'À améliorer'),
        (3, 'Satisfaisant'),
        (4, 'Bien'),
        (5, 'Excellent'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_reviews',
    )
    review_date = models.DateField()
    period_label = models.CharField(max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, default=3)
    strengths = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    goals = models.TextField(blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performance_reviews_given',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-review_date', '-id']

    def __str__(self):
        return f'Éval {self.user_id} {self.review_date}'


class TrainingRecord(models.Model):
    """Formations."""
    STATUS_PLANNED = 'planned'
    STATUS_ONGOING = 'ongoing'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = (
        (STATUS_PLANNED, 'Planifiée'),
        (STATUS_ONGOING, 'En cours'),
        (STATUS_DONE, 'Terminée'),
        (STATUS_CANCELLED, 'Annulée'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='training_records',
    )
    title = models.CharField(max_length=180)
    provider = models.CharField(max_length=180, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_records_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.title


class DisciplinaryAction(models.Model):
    """Sanctions / avertissements."""
    KIND_WARNING = 'warning'
    KIND_WRITTEN = 'written'
    KIND_SUSPENSION = 'suspension'
    KIND_OTHER = 'other'
    KIND_CHOICES = (
        (KIND_WARNING, 'Avertissement oral'),
        (KIND_WRITTEN, 'Avertissement écrit'),
        (KIND_SUSPENSION, 'Suspension'),
        (KIND_OTHER, 'Autre'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='disciplinary_actions',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_WARNING)
    action_date = models.DateField()
    reason = models.TextField()
    decision = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='disciplinary_actions_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-action_date', '-id']

    def __str__(self):
        return f'{self.get_kind_display()} — {self.user_id}'
