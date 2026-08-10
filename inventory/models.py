from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F


ITEM_CATEGORY_CHOICES = (
    ('raw', 'Matières premières'),
    ('finished', 'Produits finis'),
    ('consumable', 'Consommables'),
    ('spare', 'Pièces détachées'),
)

MOVEMENT_TYPE_CHOICES = (
    ('in', 'Entrée'),
    ('out', 'Sortie'),
    ('adjust', 'Ajustement inventaire'),
)

PURCHASE_STATUS_CHOICES = (
    ('proposed', 'Proposée'),
    ('approved', 'Approuvée'),
    ('ordered', 'Commandée'),
    ('received', 'Reçue'),
    ('cancelled', 'Annulée'),
)

UNIT_CHOICES = (
    ('feuille', 'Feuille'),
    ('pcs', 'Pièce'),
    ('m', 'Mètre'),
    ('m2', 'm²'),
    ('kg', 'Kg'),
    ('L', 'Litre'),
    ('boite', 'Boîte'),
    ('rouleau', 'Rouleau'),
    ('autre', 'Autre'),
)


class Supplier(models.Model):
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class StockItem(models.Model):
    name = models.CharField(max_length=180)
    category = models.CharField(max_length=20, choices=ITEM_CATEGORY_CHOICES, default='raw')
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='pcs')
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    min_stock = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    max_stock = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
    )
    sku = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_stock_items',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['quantity', 'min_stock']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_critical(self):
        return self.quantity <= self.min_stock

    @property
    def is_over_max(self):
        return self.max_stock > 0 and self.quantity > self.max_stock

    @property
    def stock_status(self):
        if self.is_critical:
            return 'critical'
        if self.is_over_max:
            return 'over'
        return 'ok'

    @property
    def suggested_order_qty(self):
        """Quantité suggérée pour remonter au max (ou au minimum + marge)."""
        if self.max_stock and self.max_stock > self.quantity:
            return self.max_stock - self.quantity
        if self.min_stock > 0:
            target = self.min_stock * Decimal('2')
            if target > self.quantity:
                return target - self.quantity
        return Decimal('1.00')


class StockMovement(models.Model):
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.get_movement_type_display()} {self.quantity} — {self.item.name}'


class PurchaseRequest(models.Model):
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='purchase_requests')
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests',
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=PURCHASE_STATUS_CHOICES, default='proposed')
    reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    auto_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'DA {self.item.name} × {self.quantity} ({self.status})'


def apply_stock_movement(item, *, movement_type, quantity, user=None, reference='', notes=''):
    """Applique un mouvement et met à jour le stock. Retourne (movement, purchase_request|None)."""
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise ValueError('La quantité doit être supérieure à 0.')

    if movement_type == 'in':
        item.quantity = F('quantity') + quantity
    elif movement_type == 'out':
        if item.quantity < quantity:
            raise ValueError('Stock insuffisant pour cette sortie.')
        item.quantity = F('quantity') - quantity
    elif movement_type == 'adjust':
        item.quantity = quantity
    else:
        raise ValueError('Type de mouvement invalide.')

    item.save(update_fields=['quantity', 'updated_at'])
    item.refresh_from_db()

    movement = StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=quantity if movement_type != 'adjust' else item.quantity,
        balance_after=item.quantity,
        reference=(reference or '')[:120],
        notes=notes or '',
        created_by=user,
    )

    purchase = maybe_propose_purchase(item, user=user)
    return movement, purchase


def maybe_propose_purchase(item, *, user=None):
    """Si stock ≤ minimum, propose automatiquement une demande d'achat (si aucune ouverte)."""
    if not item.is_critical:
        return None

    open_exists = item.purchase_requests.filter(
        status__in=['proposed', 'approved', 'ordered']
    ).exists()
    if open_exists:
        return None

    qty = item.suggested_order_qty
    if qty <= 0:
        qty = Decimal('1.00')

    return PurchaseRequest.objects.create(
        item=item,
        supplier=item.supplier,
        quantity=qty,
        status='proposed',
        reason=(
            f'Stock critique : {item.quantity} {item.get_unit_display()} '
            f'(minimum {item.min_stock}).'
        ),
        auto_generated=True,
        created_by=user,
    )
