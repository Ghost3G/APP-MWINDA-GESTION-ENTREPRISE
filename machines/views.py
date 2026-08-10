from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from users.permissions import can_edit_machines
from users.uploads import validate_image_upload

from .models import (
    CONSUMABLE_UNIT_CHOICES,
    MACHINE_STATUS_CHOICES,
    Machine,
    MachineBreakdown,
    MachineConsumable,
    MachineMaintenanceLog,
    MachinePartReplacement,
)


def _parse_decimal(raw, default='0'):
    text = (raw or '').strip().replace(',', '.') or default
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None


def _parse_date(raw):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None


def _deny_write(request, *redirect_args):
    messages.error(
        request,
        "La mise à jour du parc machines est réservée au service technique autorisé.",
    )
    if redirect_args:
        return redirect(*redirect_args)
    return redirect('machines_list')


def _apply_machine_photo(machine, request):
    """Met à jour ou retire la photo. Retourne un message d'erreur ou None."""
    if request.POST.get('remove_photo') == '1' and machine.photo:
        try:
            machine.photo.delete(save=False)
        except Exception:
            pass
        machine.photo = None
        return None

    photo = request.FILES.get('photo')
    if not photo:
        return None
    error = validate_image_upload(photo)
    if error:
        return error
    if machine.photo:
        try:
            machine.photo.delete(save=False)
        except Exception:
            pass
    machine.photo = photo
    return None


@login_required(login_url='login')
def machines_list(request):
    can_write = can_edit_machines(request.user)
    today = timezone.localdate()
    soon = today + timedelta(days=7)
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    alert = request.GET.get('alert', '').strip()

    if request.method == 'POST':
        if not can_write:
            return _deny_write(request)
        action = request.POST.get('action', '').strip()
        if action == 'create_machine':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Le nom de la machine est obligatoire.")
                return redirect('machines_list')
            machine_status = request.POST.get('status', 'ok').strip() or 'ok'
            if machine_status not in {c[0] for c in MACHINE_STATUS_CHOICES}:
                machine_status = 'ok'
            hours = _parse_decimal(request.POST.get('operating_hours'), '0')
            if hours is None:
                messages.error(request, "Vérifiez les heures de fonctionnement.")
                return redirect('machines_list')
            machine = Machine(
                name=name,
                brand=request.POST.get('brand', '').strip()[:120],
                model=request.POST.get('model', '').strip()[:120],
                serial_number=request.POST.get('serial_number', '').strip()[:120],
                operating_hours=hours,
                last_maintenance=_parse_date(request.POST.get('last_maintenance')),
                next_maintenance=_parse_date(request.POST.get('next_maintenance')),
                status=machine_status,
                notes=request.POST.get('notes', '').strip(),
                created_by=request.user,
            )
            photo_error = _apply_machine_photo(machine, request)
            if photo_error:
                messages.error(request, photo_error)
                return redirect('machines_list')
            machine.save()
            messages.success(request, f'Machine « {name} » ajoutée.')
            return redirect('machines_list')

        if action == 'delete_machine':
            machine = get_object_or_404(
                Machine, id=request.POST.get('machine_id'), is_active=True
            )
            confirm = request.POST.get('confirm', '').strip().upper()
            if confirm != 'SUPPRIMER':
                messages.error(
                    request,
                    "Pour supprimer, confirmez en tapant SUPPRIMER.",
                )
                return redirect('machines_list')
            label = machine.name
            machine.is_active = False
            machine.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, f'Machine « {label} » supprimée du parc.')
            return redirect('machines_list')

        messages.error(request, "Action non reconnue.")
        return redirect('machines_list')

    machines = (
        Machine.objects.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                'consumables',
                queryset=MachineConsumable.objects.filter(
                    Q(needs_replacement=True) | Q(quantity__lte=F('min_quantity'))
                ),
                to_attr='alert_consumables',
            ),
            Prefetch(
                'breakdowns',
                queryset=MachineBreakdown.objects.filter(resolved_at__isnull=True),
                to_attr='open_breakdowns',
            ),
        )
        .order_by('name')
    )
    if q:
        machines = machines.filter(
            Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(model__icontains=q)
            | Q(serial_number__icontains=q)
        )
    if status in {c[0] for c in MACHINE_STATUS_CHOICES}:
        machines = machines.filter(status=status)

    all_machines = list(machines)

    maintenance_alerts = []
    broken_alerts = []
    part_alerts = []
    for m in all_machines:
        if m.is_broken:
            broken_alerts.append(m)
        if m.maintenance_soon or m.maintenance_overdue:
            maintenance_alerts.append(m)
        if m.has_part_to_replace:
            part_alerts.append(m)

    if alert == 'maintenance':
        machines = [m for m in all_machines if m.maintenance_soon or m.maintenance_overdue]
    elif alert == 'broken':
        machines = [m for m in all_machines if m.is_broken]
    elif alert == 'part':
        machines = [m for m in all_machines if m.has_part_to_replace]
    else:
        machines = all_machines

    return render(
        request,
        'machines/machines_list.html',
        {
            'machines': machines,
            'machines_total': len(all_machines),
            'can_edit_machines': can_write,
            'search_q': q,
            'selected_status': status,
            'selected_alert': alert,
            'status_choices': MACHINE_STATUS_CHOICES,
            'maintenance_alerts': maintenance_alerts,
            'broken_alerts': broken_alerts,
            'part_alerts': part_alerts,
            'today': today,
            'soon': soon,
        },
    )


@login_required(login_url='login')
def machine_detail(request, machine_id):
    machine = get_object_or_404(
        Machine.objects.prefetch_related(
            'breakdowns',
            'part_replacements',
            'maintenance_logs',
            'consumables',
        ),
        id=machine_id,
        is_active=True,
    )
    can_write = can_edit_machines(request.user)

    if request.method == 'POST':
        if not can_write:
            return _deny_write(request, 'machine_detail', machine.id)
        action = request.POST.get('action', '').strip()

        if action == 'update_machine':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Le nom est obligatoire.")
                return redirect('machine_detail', machine_id=machine.id)
            machine_status = request.POST.get('status', machine.status).strip()
            if machine_status not in {c[0] for c in MACHINE_STATUS_CHOICES}:
                machine_status = machine.status
            hours = _parse_decimal(
                request.POST.get('operating_hours'), str(machine.operating_hours)
            )
            if hours is None:
                messages.error(request, "Vérifiez les heures de fonctionnement.")
                return redirect('machine_detail', machine_id=machine.id)
            machine.name = name
            machine.brand = request.POST.get('brand', '').strip()[:120]
            machine.model = request.POST.get('model', '').strip()[:120]
            machine.serial_number = request.POST.get('serial_number', '').strip()[:120]
            machine.operating_hours = hours
            machine.last_maintenance = _parse_date(request.POST.get('last_maintenance'))
            machine.next_maintenance = _parse_date(request.POST.get('next_maintenance'))
            machine.status = machine_status
            machine.notes = request.POST.get('notes', '').strip()
            photo_error = _apply_machine_photo(machine, request)
            if photo_error:
                messages.error(request, photo_error)
                return redirect('machine_detail', machine_id=machine.id)
            machine.save()
            messages.success(request, "Fiche machine mise à jour.")
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'add_breakdown':
            title = request.POST.get('title', '').strip()
            if not title:
                messages.error(request, "Indiquez le titre de la panne.")
                return redirect('machine_detail', machine_id=machine.id)
            cost = _parse_decimal(request.POST.get('cost'), '0') or Decimal('0')
            started = _parse_date(request.POST.get('started_at')) or timezone.localdate()
            MachineBreakdown.objects.create(
                machine=machine,
                title=title,
                description=request.POST.get('description', '').strip(),
                started_at=started,
                cost=cost,
                created_by=request.user,
            )
            machine.status = 'broken'
            machine.save(update_fields=['status', 'updated_at'])
            messages.warning(request, f'Panne enregistrée : {title}.')
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'resolve_breakdown':
            breakdown = get_object_or_404(
                MachineBreakdown, id=request.POST.get('breakdown_id'), machine=machine
            )
            resolved = _parse_date(request.POST.get('resolved_at')) or timezone.localdate()
            cost = _parse_decimal(request.POST.get('cost'), str(breakdown.cost))
            if cost is not None:
                breakdown.cost = cost
            breakdown.resolved_at = resolved
            breakdown.save()
            if not machine.breakdowns.filter(resolved_at__isnull=True).exists():
                machine.status = 'ok'
                machine.save(update_fields=['status', 'updated_at'])
            messages.success(request, "Panne clôturée.")
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'add_part':
            part_name = request.POST.get('part_name', '').strip()
            if not part_name:
                messages.error(request, "Nom de la pièce obligatoire.")
                return redirect('machine_detail', machine_id=machine.id)
            cost = _parse_decimal(request.POST.get('cost'), '0') or Decimal('0')
            hours = _parse_decimal(request.POST.get('operating_hours_at'))
            MachinePartReplacement.objects.create(
                machine=machine,
                part_name=part_name,
                replaced_at=_parse_date(request.POST.get('replaced_at'))
                or timezone.localdate(),
                cost=cost,
                operating_hours_at=hours,
                notes=request.POST.get('notes', '').strip(),
                created_by=request.user,
            )
            messages.success(request, f'Pièce remplacée : {part_name}.')
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'add_maintenance':
            performed = _parse_date(request.POST.get('performed_at')) or timezone.localdate()
            next_due = _parse_date(request.POST.get('next_due'))
            cost = _parse_decimal(request.POST.get('cost'), '0') or Decimal('0')
            hours = _parse_decimal(request.POST.get('operating_hours_at'))
            MachineMaintenanceLog.objects.create(
                machine=machine,
                title=request.POST.get('title', '').strip()[:180],
                performed_at=performed,
                next_due=next_due,
                cost=cost,
                operating_hours_at=hours,
                notes=request.POST.get('notes', '').strip(),
                created_by=request.user,
            )
            machine.last_maintenance = performed
            if next_due:
                machine.next_maintenance = next_due
            if hours is not None:
                machine.operating_hours = hours
            machine.save()
            messages.success(request, "Intervention ajoutée à l’historique de maintenance.")
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'add_consumable':
            name = request.POST.get('name', '').strip()
            if not name:
                messages.error(request, "Nom du consommable obligatoire.")
                return redirect('machine_detail', machine_id=machine.id)
            qty = _parse_decimal(request.POST.get('quantity'), '0')
            min_q = _parse_decimal(request.POST.get('min_quantity'), '0')
            if qty is None or min_q is None:
                messages.error(request, "Quantités invalides.")
                return redirect('machine_detail', machine_id=machine.id)
            unit = request.POST.get('unit', 'pcs').strip() or 'pcs'
            if unit not in {c[0] for c in CONSUMABLE_UNIT_CHOICES}:
                unit = 'pcs'
            MachineConsumable.objects.create(
                machine=machine,
                name=name,
                quantity=qty,
                min_quantity=min_q,
                unit=unit,
                needs_replacement=request.POST.get('needs_replacement') == '1',
                notes=request.POST.get('notes', '').strip(),
            )
            messages.success(request, f'Consommable « {name} » ajouté.')
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'update_consumable':
            consumable = get_object_or_404(
                MachineConsumable, id=request.POST.get('consumable_id'), machine=machine
            )
            qty = _parse_decimal(request.POST.get('quantity'), str(consumable.quantity))
            min_q = _parse_decimal(
                request.POST.get('min_quantity'), str(consumable.min_quantity)
            )
            if qty is None or min_q is None:
                messages.error(request, "Quantités invalides.")
                return redirect('machine_detail', machine_id=machine.id)
            consumable.quantity = qty
            consumable.min_quantity = min_q
            consumable.needs_replacement = request.POST.get('needs_replacement') == '1'
            consumable.save()
            messages.success(request, f'Consommable « {consumable.name} » mis à jour.')
            return redirect('machine_detail', machine_id=machine.id)

        if action == 'delete_machine':
            confirm = request.POST.get('confirm', '').strip().upper()
            if confirm != 'SUPPRIMER':
                messages.error(request, "Pour supprimer, confirmez en tapant SUPPRIMER.")
                return redirect('machine_detail', machine_id=machine.id)
            label = machine.name
            machine.is_active = False
            machine.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, f'Machine « {label} » supprimée du parc.')
            return redirect('machines_list')

        messages.error(request, "Action non reconnue.")
        return redirect('machine_detail', machine_id=machine.id)

    return render(
        request,
        'machines/machine_detail.html',
        {
            'machine': machine,
            'can_edit_machines': can_write,
            'status_choices': MACHINE_STATUS_CHOICES,
            'unit_choices': CONSUMABLE_UNIT_CHOICES,
            'breakdowns': machine.breakdowns.all()[:40],
            'parts': machine.part_replacements.all()[:40],
            'maintenances': machine.maintenance_logs.all()[:40],
            'consumables': machine.consumables.all(),
            'maintenance_cost_total': machine.maintenance_cost_total,
        },
    )
