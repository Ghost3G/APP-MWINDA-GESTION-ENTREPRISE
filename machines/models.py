from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q, Sum
from django.utils import timezone


MACHINE_STATUS_CHOICES = (
    ('ok', 'En service'),
    ('broken', 'En panne'),
    ('standby', 'Hors service'),
)

CONSUMABLE_UNIT_CHOICES = (
    ('pcs', 'Pièce'),
    ('L', 'Litre'),
    ('ml', 'ml'),
    ('kg', 'Kg'),
    ('rouleau', 'Rouleau'),
    ('autre', 'Autre'),
)


class Machine(models.Model):
    name = models.CharField(max_length=180)
    brand = models.CharField(max_length=120, blank=True)
    model = models.CharField(max_length=120, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(
        null=True,
        blank=True,
        help_text='Fin de garantie',
    )
    operating_hours = models.DecimalField(
        max_digits=12, decimal_places=1, default=Decimal('0.0')
    )
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=MACHINE_STATUS_CHOICES, default='ok'
    )
    photo = models.ImageField(
        upload_to='machine_photos/',
        blank=True,
        null=True,
        verbose_name='Photo de la machine',
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_machines',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        indexes = [
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['next_maintenance']),
        ]

    def __str__(self):
        return self.name

    @property
    def photo_url(self):
        try:
            if not self.photo:
                return ''
            name = (getattr(self.photo, 'name', None) or '').strip()
            if not name:
                return ''
            if name.startswith('http://') or name.startswith('https://'):
                return name
            try:
                import os

                import cloudinary
                from django.conf import settings as django_settings

                if getattr(django_settings, 'CLOUDINARY_STORAGE', None) or os.environ.get(
                    'CLOUDINARY_URL'
                ):
                    return cloudinary.CloudinaryResource(
                        name,
                        resource_type='image',
                    ).build_url(secure=True)
            except Exception:
                pass
            return self.photo.url
        except Exception:
            return ''

    @property
    def maintenance_cost_total(self):
        from_logs = self.maintenance_logs.aggregate(total=Sum('cost'))['total'] or Decimal('0')
        from_parts = self.part_replacements.aggregate(total=Sum('cost'))['total'] or Decimal('0')
        from_breakdowns = self.breakdowns.aggregate(total=Sum('cost'))['total'] or Decimal('0')
        return from_logs + from_parts + from_breakdowns

    @property
    def is_broken(self):
        if self.status == 'broken':
            return True
        return self.breakdowns.filter(resolved_at__isnull=True).exists()

    @property
    def days_until_maintenance(self):
        if not self.next_maintenance:
            return None
        return (self.next_maintenance - timezone.localdate()).days

    @property
    def maintenance_soon(self):
        days = self.days_until_maintenance
        return days is not None and 0 <= days <= 7

    @property
    def maintenance_overdue(self):
        days = self.days_until_maintenance
        return days is not None and days < 0

    @property
    def has_part_to_replace(self):
        return self.consumables.filter(
            Q(needs_replacement=True) | Q(quantity__lte=F('min_quantity'))
        ).exists()

    @property
    def alert_level(self):
        if self.is_broken:
            return 'broken'
        if self.has_part_to_replace:
            return 'part'
        if self.maintenance_overdue or self.maintenance_soon:
            return 'maintenance'
        return 'ok'


class MachineBreakdown(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='breakdowns')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    started_at = models.DateField(default=timezone.localdate)
    resolved_at = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine_breakdowns',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at', '-id']

    def __str__(self):
        return f'{self.machine.name} — {self.title}'

    @property
    def is_open(self):
        return self.resolved_at is None


class MachinePartReplacement(models.Model):
    machine = models.ForeignKey(
        Machine, on_delete=models.CASCADE, related_name='part_replacements'
    )
    part_name = models.CharField(max_length=180)
    replaced_at = models.DateField(default=timezone.localdate)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    operating_hours_at = models.DecimalField(
        max_digits=12, decimal_places=1, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine_part_replacements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-replaced_at', '-id']

    def __str__(self):
        return f'{self.part_name} — {self.machine.name}'


class MachineMaintenanceLog(models.Model):
    machine = models.ForeignKey(
        Machine, on_delete=models.CASCADE, related_name='maintenance_logs'
    )
    performed_at = models.DateField(default=timezone.localdate)
    next_due = models.DateField(null=True, blank=True)
    cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    operating_hours_at = models.DecimalField(
        max_digits=12, decimal_places=1, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='machine_maintenance_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at', '-id']

    def __str__(self):
        return f'Maintenance {self.machine.name} — {self.performed_at}'


class MachineConsumable(models.Model):
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name='consumables')
    name = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    min_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00')
    )
    unit = models.CharField(max_length=20, choices=CONSUMABLE_UNIT_CHOICES, default='pcs')
    needs_replacement = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return f'{self.name} ({self.machine.name})'

    @property
    def is_low(self):
        return self.quantity <= self.min_quantity

    @property
    def alert_replace(self):
        return self.needs_replacement or self.is_low
