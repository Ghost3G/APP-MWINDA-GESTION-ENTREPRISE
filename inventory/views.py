from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from users.permissions import can_access_stock, can_edit_stock, is_stock_manager

from .models import (
    ITEM_CATEGORY_CHOICES,
    MOVEMENT_TYPE_CHOICES,
    PURCHASE_STATUS_CHOICES,
    UNIT_CHOICES,
    PurchaseRequest,
    StockItem,
    StockMovement,
    Supplier,
    apply_stock_movement,
    maybe_propose_purchase,
)


def _deny(request):
    messages.error(
        request,
        "Accès Stock & Achats réservé à la direction et au service logistique autorisé.",
    )
    return redirect('dashboard')


def _parse_decimal(raw, default='0'):
    text = (raw or '').strip().replace(',', '.') or default
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None


@login_required(login_url='login')
def stock_dashboard(request):
    if not can_access_stock(request.user):
        return _deny(request)

    can_write = can_edit_stock(request.user)
    category = request.GET.get('category', '').strip()
    q = request.GET.get('q', '').strip()
    critical_only = request.GET.get('critical', '').strip() == '1'

    if request.method == 'POST':
        if not can_write:
            messages.error(request, "Vous n’avez pas le droit de modifier le stock.")
            return redirect('stock_dashboard')

        action = request.POST.get('action', '').strip()

        if action == 'create_item':
            name = request.POST.get('name', '').strip()
            item_category = request.POST.get('category', 'raw').strip() or 'raw'
            unit = request.POST.get('unit', 'pcs').strip() or 'pcs'
            quantity = _parse_decimal(request.POST.get('quantity'), '0')
            min_stock = _parse_decimal(request.POST.get('min_stock'), '0')
            max_stock = _parse_decimal(request.POST.get('max_stock'), '0')
            supplier_id = request.POST.get('supplier_id', '').strip()
            if not name or quantity is None or min_stock is None or max_stock is None:
                messages.error(request, "Vérifiez le nom et les quantités de l’article.")
                return redirect('stock_dashboard')
            if item_category not in {c[0] for c in ITEM_CATEGORY_CHOICES}:
                item_category = 'raw'
            if unit not in {c[0] for c in UNIT_CHOICES}:
                unit = 'pcs'
            supplier = Supplier.objects.filter(id=supplier_id, is_active=True).first() if supplier_id else None
            item = StockItem.objects.create(
                name=name,
                category=item_category,
                unit=unit,
                quantity=quantity,
                min_stock=min_stock,
                max_stock=max_stock,
                supplier=supplier,
                sku=request.POST.get('sku', '').strip()[:60],
                notes=request.POST.get('notes', '').strip(),
                created_by=request.user,
            )
            purchase = maybe_propose_purchase(item, user=request.user)
            messages.success(request, f'Article « {item.name} » créé.')
            if purchase:
                messages.warning(
                    request,
                    f'Stock critique : demande d’achat automatique proposée '
                    f'({purchase.quantity} {item.get_unit_display()}).',
                )
            return redirect('stock_dashboard')

        if action == 'create_supplier':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Le nom du fournisseur est obligatoire.")
                return redirect('stock_dashboard')
            Supplier.objects.create(
                name=name,
                phone=request.POST.get('phone', '').strip()[:40],
                email=request.POST.get('email', '').strip(),
                address=request.POST.get('address', '').strip()[:255],
                notes=request.POST.get('notes', '').strip(),
            )
            messages.success(request, f'Fournisseur « {name} » ajouté.')
            return redirect('stock_dashboard')

        if action == 'movement':
            item = get_object_or_404(StockItem, id=request.POST.get('item_id'), is_active=True)
            movement_type = request.POST.get('movement_type', '').strip()
            quantity = _parse_decimal(request.POST.get('quantity'))
            if movement_type not in {c[0] for c in MOVEMENT_TYPE_CHOICES} or quantity is None:
                messages.error(request, "Mouvement invalide.")
                return redirect('stock_dashboard')
            try:
                movement, purchase = apply_stock_movement(
                    item,
                    movement_type=movement_type,
                    quantity=quantity,
                    user=request.user,
                    reference=request.POST.get('reference', '').strip(),
                    notes=request.POST.get('notes', '').strip(),
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('stock_dashboard')
            messages.success(
                request,
                f'{movement.get_movement_type_display()} enregistrée — '
                f'stock « {item.name} » = {item.quantity} {item.get_unit_display()}.',
            )
            if purchase:
                messages.warning(
                    request,
                    f'🔴 STOCK CRITIQUE — demande d’achat proposée automatiquement '
                    f'({purchase.quantity} {item.get_unit_display()}).',
                )
            return redirect('stock_dashboard')

        if action == 'propose_purchase':
            item = get_object_or_404(StockItem, id=request.POST.get('item_id'), is_active=True)
            quantity = _parse_decimal(request.POST.get('quantity'), str(item.suggested_order_qty))
            if quantity is None or quantity <= 0:
                messages.error(request, "Quantité de commande invalide.")
                return redirect('stock_dashboard')
            purchase = PurchaseRequest.objects.create(
                item=item,
                supplier=item.supplier,
                quantity=quantity,
                status='proposed',
                reason=request.POST.get('reason', '').strip()
                or f'Reapprovisionnement — stock actuel {item.quantity}.',
                auto_generated=False,
                created_by=request.user,
            )
            messages.success(
                request,
                f'Demande d’achat créée pour « {item.name} » ({purchase.quantity} {item.get_unit_display()}).',
            )
            return redirect('stock_dashboard')

        if action == 'update_purchase_status':
            purchase = get_object_or_404(PurchaseRequest, id=request.POST.get('purchase_id'))
            new_status = request.POST.get('status', '').strip()
            if new_status not in {c[0] for c in PURCHASE_STATUS_CHOICES}:
                messages.error(request, "Statut invalide.")
                return redirect('stock_dashboard')
            previous = purchase.status
            purchase.status = new_status
            purchase.save(update_fields=['status', 'updated_at'])
            if new_status == 'received' and previous != 'received':
                apply_stock_movement(
                    purchase.item,
                    movement_type='in',
                    quantity=purchase.quantity,
                    user=request.user,
                    reference=f'DA#{purchase.id}',
                    notes='Réception demande d’achat',
                )  # ignore proposed purchase return
                messages.success(
                    request,
                    f'Demande #{purchase.id} reçue — entrée stock enregistrée '
                    f'({purchase.quantity} {purchase.item.get_unit_display()}).',
                )
            else:
                messages.success(request, f'Demande #{purchase.id} → {purchase.get_status_display()}.')
            return redirect('stock_dashboard')

        messages.error(request, "Action non reconnue.")
        return redirect('stock_dashboard')

    all_items = list(
        StockItem.objects.filter(is_active=True).select_related('supplier')
    )
    items = all_items
    if category:
        items = [i for i in items if i.category == category]
    if q:
        q_lower = q.lower()
        items = [
            i for i in items
            if q_lower in (i.name or '').lower()
            or q_lower in (i.sku or '').lower()
            or q_lower in (i.notes or '').lower()
        ]
    if critical_only:
        items = [item for item in items if item.is_critical]

    # Tri : critiques d'abord
    items.sort(key=lambda i: (0 if i.is_critical else 1, i.name.lower()))

    critical_items = [i for i in all_items if i.is_critical]
    suppliers = list(Supplier.objects.filter(is_active=True))
    movements = StockMovement.objects.select_related('item', 'created_by')[:20]
    purchases = PurchaseRequest.objects.select_related('item', 'supplier', 'created_by').exclude(
        status='cancelled'
    )[:30]
    open_purchases = PurchaseRequest.objects.filter(
        status__in=['proposed', 'approved', 'ordered']
    ).count()

    return render(request, 'inventory/stock.html', {
        'items': items,
        'all_items': all_items,
        'critical_items': critical_items,
        'critical_count': len(critical_items),
        'suppliers': suppliers,
        'movements': movements,
        'purchases': purchases,
        'open_purchases': open_purchases,
        'category_choices': ITEM_CATEGORY_CHOICES,
        'unit_choices': UNIT_CHOICES,
        'movement_type_choices': MOVEMENT_TYPE_CHOICES,
        'purchase_status_choices': PURCHASE_STATUS_CHOICES,
        'selected_category': category,
        'search_q': q,
        'critical_only': critical_only,
        'can_edit_stock': can_write,
        'is_stock_manager_user': is_stock_manager(request.user),
        'stock_section': 'dashboard',
    })
