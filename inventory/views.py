from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from projects.models import Project
from users.permissions import can_access_stock, can_edit_stock, is_stock_manager

from .models import (
    DELIVERY_STATUS_CHOICES,
    ITEM_CATEGORY_CHOICES,
    MOVEMENT_TYPE_CHOICES,
    PURCHASE_STATUS_CHOICES,
    SUPPLIER_SPECIALTY_CHOICES,
    UNIT_CHOICES,
    DeliveryShipment,
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
    purchase_status_rows = list(
        PurchaseRequest.objects.exclude(status='cancelled')
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    from reports.chart_data import build_stock_charts

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
        'mw_charts': build_stock_charts(all_items, purchase_status_rows=purchase_status_rows),
    })


def _parse_date(raw):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None


@login_required(login_url='login')
def stock_suppliers(request):
    if not can_access_stock(request.user):
        return _deny(request)

    can_write = can_edit_stock(request.user)
    q = request.GET.get('q', '').strip()
    specialty = request.GET.get('specialty', '').strip()
    show_inactive = request.GET.get('inactive', '').strip() == '1'

    if request.method == 'POST':
        if not can_write:
            messages.error(request, "Vous n’avez pas le droit de modifier les fournisseurs.")
            return redirect('stock_suppliers')

        action = request.POST.get('action', '').strip()
        specialty_value = request.POST.get('specialty', 'other').strip() or 'other'
        if specialty_value not in {c[0] for c in SUPPLIER_SPECIALTY_CHOICES}:
            specialty_value = 'other'
        lead_raw = request.POST.get('lead_time_days', '0').strip() or '0'
        try:
            lead_time = max(0, int(lead_raw))
        except ValueError:
            lead_time = 0

        payload = {
            'name': request.POST.get('name', '').strip(),
            'contact_name': request.POST.get('contact_name', '').strip()[:120],
            'phone': request.POST.get('phone', '').strip()[:40],
            'email': request.POST.get('email', '').strip(),
            'city': request.POST.get('city', '').strip()[:80],
            'address': request.POST.get('address', '').strip()[:255],
            'specialty': specialty_value,
            'lead_time_days': lead_time,
            'payment_terms': request.POST.get('payment_terms', '').strip()[:120],
            'notes': request.POST.get('notes', '').strip(),
        }

        if action == 'create_supplier':
            if not payload['name']:
                messages.error(request, "Le nom du fournisseur est obligatoire.")
                return redirect('stock_suppliers')
            Supplier.objects.create(**payload)
            messages.success(request, f'Fournisseur « {payload["name"]} » enregistré.')
            return redirect('stock_suppliers')

        if action == 'update_supplier':
            supplier = get_object_or_404(Supplier, id=request.POST.get('supplier_id'))
            if not payload['name']:
                messages.error(request, "Le nom du fournisseur est obligatoire.")
                return redirect('stock_suppliers')
            for field, value in payload.items():
                setattr(supplier, field, value)
            supplier.is_active = request.POST.get('is_active') == '1'
            supplier.save()
            messages.success(request, f'Fournisseur « {supplier.name} » mis à jour.')
            return redirect('stock_suppliers')

        if action == 'toggle_supplier':
            supplier = get_object_or_404(Supplier, id=request.POST.get('supplier_id'))
            supplier.is_active = not supplier.is_active
            supplier.save(update_fields=['is_active', 'updated_at'])
            state = 'réactivé' if supplier.is_active else 'désactivé'
            messages.success(request, f'Fournisseur « {supplier.name} » {state}.')
            return redirect('stock_suppliers')

        messages.error(request, "Action non reconnue.")
        return redirect('stock_suppliers')

    suppliers = Supplier.objects.annotate(
        items_count=Count('items', filter=Q(items__is_active=True)),
        purchases_count=Count('purchase_requests'),
    )
    if not show_inactive:
        suppliers = suppliers.filter(is_active=True)
    if specialty in {c[0] for c in SUPPLIER_SPECIALTY_CHOICES}:
        suppliers = suppliers.filter(specialty=specialty)
    if q:
        suppliers = suppliers.filter(
            Q(name__icontains=q)
            | Q(contact_name__icontains=q)
            | Q(city__icontains=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )

    return render(request, 'inventory/suppliers.html', {
        'suppliers': suppliers,
        'specialty_choices': SUPPLIER_SPECIALTY_CHOICES,
        'search_q': q,
        'selected_specialty': specialty,
        'show_inactive': show_inactive,
        'can_edit_stock': can_write,
        'is_stock_manager_user': is_stock_manager(request.user),
        'stock_section': 'suppliers',
    })


@login_required(login_url='login')
def stock_logistics(request):
    if not can_access_stock(request.user):
        return _deny(request)

    can_write = can_edit_stock(request.user)
    today = timezone.localdate()

    if request.method == 'POST':
        if not can_write:
            messages.error(request, "Vous n’avez pas le droit de modifier la logistique.")
            return redirect('stock_logistics')

        action = request.POST.get('action', '').strip()

        if action == 'create_delivery':
            project = get_object_or_404(Project, id=request.POST.get('project_id'))
            status = request.POST.get('status', 'pending').strip() or 'pending'
            if status not in {c[0] for c in DELIVERY_STATUS_CHOICES}:
                status = 'pending'
            scheduled = _parse_date(request.POST.get('scheduled_date'))
            shipment = DeliveryShipment.objects.create(
                project=project,
                status=status,
                scheduled_date=scheduled,
                driver_name=request.POST.get('driver_name', '').strip()[:120],
                recipient_name=request.POST.get('recipient_name', '').strip()[:120],
                destination=request.POST.get('destination', '').strip()[:255],
                notes=request.POST.get('notes', '').strip(),
                created_by=request.user,
            )
            if status == 'delivered':
                shipment.delivered_at = timezone.now()
                shipment.save(update_fields=['delivered_at', 'updated_at'])
            messages.success(request, f'Livraison créée pour « {project.name} ».')
            return redirect('stock_logistics')

        if action == 'update_delivery':
            shipment = get_object_or_404(DeliveryShipment, id=request.POST.get('delivery_id'))
            status = request.POST.get('status', shipment.status).strip()
            if status not in {c[0] for c in DELIVERY_STATUS_CHOICES}:
                messages.error(request, "Statut de livraison invalide.")
                return redirect('stock_logistics')
            shipment.status = status
            shipment.scheduled_date = _parse_date(request.POST.get('scheduled_date')) or shipment.scheduled_date
            shipment.driver_name = request.POST.get('driver_name', shipment.driver_name).strip()[:120]
            shipment.recipient_name = request.POST.get('recipient_name', shipment.recipient_name).strip()[:120]
            shipment.destination = request.POST.get('destination', shipment.destination).strip()[:255]
            shipment.notes = request.POST.get('notes', shipment.notes).strip()
            if status == 'delivered' and not shipment.delivered_at:
                shipment.delivered_at = timezone.now()
            if status != 'delivered':
                shipment.delivered_at = None
            shipment.save()
            messages.success(
                request,
                f'Livraison « {shipment.project.name} » → {shipment.get_status_display()}.',
            )
            return redirect('stock_logistics')

        if action == 'receive_purchase':
            purchase = get_object_or_404(PurchaseRequest, id=request.POST.get('purchase_id'))
            if purchase.status == 'received':
                messages.info(request, "Cette commande est déjà reçue.")
                return redirect('stock_logistics')
            purchase.status = 'received'
            purchase.save(update_fields=['status', 'updated_at'])
            apply_stock_movement(
                purchase.item,
                movement_type='in',
                quantity=purchase.quantity,
                user=request.user,
                reference=f'DA#{purchase.id}',
                notes='Réception fournisseur (logistique)',
            )
            messages.success(
                request,
                f'Réception enregistrée — « {purchase.item.name} » '
                f'+{purchase.quantity} {purchase.item.get_unit_display()}.',
            )
            return redirect('stock_logistics')

        messages.error(request, "Action non reconnue.")
        return redirect('stock_logistics')

    awaiting_projects = list(
        Project.objects.filter(status='awaiting_delivery')
        .select_related('manager', 'commercial_agent', 'client')
        .prefetch_related(
            Prefetch(
                'delivery_shipments',
                queryset=DeliveryShipment.objects.exclude(status='cancelled').order_by('-created_at'),
            )
        )
        .order_by('end_date', 'name')
    )
    open_deliveries = DeliveryShipment.objects.exclude(
        status__in=['delivered', 'cancelled']
    ).select_related('project', 'created_by')
    today_deliveries = open_deliveries.filter(scheduled_date=today)
    week_end = today + timedelta(days=7)
    week_deliveries = open_deliveries.filter(
        scheduled_date__gte=today,
        scheduled_date__lte=week_end,
    ).order_by('scheduled_date')
    recent_delivered = DeliveryShipment.objects.filter(
        status='delivered'
    ).select_related('project')[:15]
    incoming_purchases = PurchaseRequest.objects.filter(
        status__in=['approved', 'ordered']
    ).select_related('item', 'supplier')[:30]
    project_choices = Project.objects.exclude(status='done').order_by('name')

    return render(request, 'inventory/logistics.html', {
        'awaiting_projects': awaiting_projects,
        'today_deliveries': today_deliveries,
        'week_deliveries': week_deliveries,
        'open_deliveries': open_deliveries.order_by('scheduled_date', '-created_at')[:40],
        'recent_delivered': recent_delivered,
        'incoming_purchases': incoming_purchases,
        'project_choices': project_choices,
        'delivery_status_choices': DELIVERY_STATUS_CHOICES,
        'today': today,
        'can_edit_stock': can_write,
        'is_stock_manager_user': is_stock_manager(request.user),
        'stock_section': 'logistics',
    })
