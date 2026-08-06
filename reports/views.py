import csv
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, Prefetch
from django.http import HttpResponse, HttpResponseForbidden

from projects.branches import TECH_BRANCH_CHOICES
from projects.models import Project
from users.permissions import (
    is_admin_user,
    is_management_user,
    is_commercial_lead,
    can_access_finance,
    can_edit_finance,
    can_manage_finance_closure,
    can_access_crm,
    can_view_all_crm_clients,
    can_reassign_crm_client,
    can_edit_crm_clients,
    can_edit_crm_client,
)
from users.uploads import validate_attachment_upload

from .models import (
    CrmFollowUp,
    DailyReport,
    FinanceClient,
    FinanceDayClosure,
    FinanceExpense,
    FinanceIncome,
    EXPENSE_CATEGORY_CHOICES,
    INCOME_CATEGORY_CHOICES,
    PAYMENT_METHOD_CHOICES,
)
from .pdf import build_report_pdf, build_finance_pdf

CLIENT_STATUS_CHOICES = getattr(
    FinanceClient._meta.get_field('status'),
    'choices',
    None,
) or (
    ('prospect', 'Prospect'),
    ('active', 'Actif'),
    ('inactive', 'Inactif'),
    ('lost', 'Perdu'),
)

User = get_user_model()

FRENCH_MONTHS = (
    '',
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
)

FRENCH_WEEKDAYS = (
    'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche',
)


def _month_label(year, month):
    return f'{FRENCH_MONTHS[month]} {year}'


def _day_label(day):
    return f'{FRENCH_WEEKDAYS[day.weekday()]} {day.day} {FRENCH_MONTHS[day.month].lower()} {day.year}'


def _group_reports_by_month(reports):
    """Agents : historiques regroupés par mois (plus récents d’abord)."""
    groups = []
    index = {}
    for report in reports:
        day = report.date
        key = f'{day.year}-{day.month:02d}'
        if key not in index:
            index[key] = len(groups)
            groups.append({
                'key': key,
                'label': _month_label(day.year, day.month),
                'sort_key': (day.year, day.month),
                'reports': [],
            })
        groups[index[key]]['reports'].append(report)

    groups.sort(key=lambda item: item['sort_key'], reverse=True)
    for group in groups:
        group['count'] = len(group['reports'])
        group.pop('sort_key', None)
    return groups


def _group_reports_by_month_then_day(reports):
    """Direction : mois → jours → rapports (plus récents d’abord)."""
    months = []
    month_index = {}
    for report in reports:
        day = report.date
        month_key = f'{day.year}-{day.month:02d}'
        if month_key not in month_index:
            month_index[month_key] = len(months)
            months.append({
                'key': month_key,
                'label': _month_label(day.year, day.month),
                'sort_key': (day.year, day.month),
                'days': [],
                '_day_index': {},
            })
        month = months[month_index[month_key]]
        day_key = day.isoformat()
        if day_key not in month['_day_index']:
            month['_day_index'][day_key] = len(month['days'])
            month['days'].append({
                'key': day_key,
                'label': _day_label(day),
                'date': day,
                'sort_key': day,
                'reports': [],
            })
        month['days'][month['_day_index'][day_key]]['reports'].append(report)

    months.sort(key=lambda item: item['sort_key'], reverse=True)
    for month in months:
        month['days'].sort(key=lambda item: item['sort_key'], reverse=True)
        for day_group in month['days']:
            day_group['count'] = len(day_group['reports'])
            day_group.pop('sort_key', None)
        month['count'] = sum(day['count'] for day in month['days'])
        month.pop('sort_key', None)
        month.pop('_day_index', None)
    return months


def _finance_access_or_redirect(request):
    can_access = can_access_finance(request.user)
    if not can_access:
        messages.error(request, "Accès réservé au service financier et à la direction.")
        return None
    return can_access


def _is_finance_day_closed(day):
    return FinanceDayClosure.objects.filter(closure_date=day).exists()


def _get_finance_day_closure(day):
    return (
        FinanceDayClosure.objects.filter(closure_date=day)
        .select_related('closed_by')
        .first()
    )


def _finance_write_guard(request, record_date):
    """Bloque l'écriture si lecture seule ou journée clôturée."""
    if not can_edit_finance(request.user):
        messages.error(request, "Accès en lecture seule. Seule l'équipe Finance peut saisir.")
        return False
    if _is_finance_day_closed(record_date):
        messages.error(
            request,
            "Cette journée est clôturée. Rouvrez-la pour modifier la caisse.",
        )
        return False
    return True


def _category_totals(model, date_field, start, end, choices):
    labels = dict(choices)
    rows = (
        model.objects.filter(**{f'{date_field}__gte': start, f'{date_field}__lte': end})
        .values('category')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    return [
        {
            'category': row['category'],
            'label': labels.get(row['category'], row['category'] or '—'),
            'total': row['total'] or Decimal('0.00'),
            'count': row['count'],
        }
        for row in rows
    ]


def _payment_method_totals(start, end):
    """Totaux entrées / sorties / net par mode de paiement sur une période."""
    labels = dict(PAYMENT_METHOD_CHOICES)
    income_rows = {
        row['payment_method']: row
        for row in (
            FinanceIncome.objects.filter(income_date__gte=start, income_date__lte=end)
            .values('payment_method')
            .annotate(total=Sum('amount'), count=Count('id'))
        )
    }
    expense_rows = {
        row['payment_method']: row
        for row in (
            FinanceExpense.objects.filter(expense_date__gte=start, expense_date__lte=end)
            .values('payment_method')
            .annotate(total=Sum('amount'), count=Count('id'))
        )
    }
    methods = set(income_rows) | set(expense_rows)
    rows = []
    for method in methods:
        in_row = income_rows.get(method, {})
        out_row = expense_rows.get(method, {})
        entrees = in_row.get('total') or Decimal('0.00')
        sorties = out_row.get('total') or Decimal('0.00')
        solde = entrees - sorties
        rows.append({
            'payment_method': method,
            'label': labels.get(method, method or '—'),
            'entrees': entrees,
            'sorties': sorties,
            'solde': solde,
            'is_gain': solde >= 0,
            'income_count': in_row.get('count') or 0,
            'expense_count': out_row.get('count') or 0,
        })
    rows.sort(key=lambda row: (-float(row['entrees'] + row['sorties']), row['label']))
    return rows


def _apply_finance_list_filters(qs, *, filter_category='', filter_project='', filter_client='', filter_payment=''):
    if filter_category:
        qs = qs.filter(category=filter_category)
    if filter_project:
        try:
            qs = qs.filter(project_id=int(filter_project))
        except (TypeError, ValueError):
            pass
    if filter_client:
        try:
            qs = qs.filter(client_id=int(filter_client))
        except (TypeError, ValueError):
            pass
    if filter_payment:
        qs = qs.filter(payment_method=filter_payment)
    return qs


def _resolve_attachment(request):
    """Retourne (file_or_None, error_message_or_None)."""
    upload = request.FILES.get('attachment')
    if not upload:
        return None, None
    error = validate_attachment_upload(upload)
    if error:
        return None, error
    return upload, None


def _parse_selected_date(value):
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


def _sum_amount(qs):
    return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')


def _finance_totals_for_date(selected):
    total_out = _sum_amount(FinanceExpense.objects.filter(expense_date=selected))
    total_in = _sum_amount(FinanceIncome.objects.filter(income_date=selected))
    solde = total_in - total_out
    return {
        'entrees': total_in,
        'sorties': total_out,
        'solde': solde,
        'solde_abs': abs(solde),
        'is_gain': solde >= 0,
    }


def _period_bounds(selected):
    month_last_day = monthrange(selected.year, selected.month)[1]
    if selected.month <= 6:
        semester_start = selected.replace(month=1, day=1)
        semester_end = selected.replace(month=6, day=30)
        semester_label = f'Semestre 1 {selected.year}'
    else:
        semester_start = selected.replace(month=7, day=1)
        semester_end = selected.replace(month=12, day=31)
        semester_label = f'Semestre 2 {selected.year}'
    return {
        'daily': (selected, selected),
        'monthly': (selected.replace(day=1), selected.replace(day=month_last_day)),
        'semestrial': (semester_start, semester_end),
        'annual': (selected.replace(month=1, day=1), selected.replace(month=12, day=31)),
        'semester_label': semester_label,
    }


def _finance_totals(start, end):
    total_out = _sum_amount(FinanceExpense.objects.filter(expense_date__gte=start, expense_date__lte=end))
    total_in = _sum_amount(FinanceIncome.objects.filter(income_date__gte=start, income_date__lte=end))
    solde = total_in - total_out
    return {
        'entrees': total_in,
        'sorties': total_out,
        'solde': solde,
        'solde_abs': abs(solde),
        'is_gain': solde >= 0,
    }


def _valid_choice(value, choices, default):
    allowed = {key for key, _label in choices}
    if value in allowed:
        return value
    return default


def _resolve_project(project_id_raw):
    project_id = (project_id_raw or '').strip()
    if not project_id:
        return None
    try:
        return Project.objects.filter(pk=int(project_id)).first()
    except (TypeError, ValueError):
        return None


def _resolve_client(client_id_raw):
    client_id = (client_id_raw or '').strip()
    if not client_id:
        return None
    try:
        return FinanceClient.objects.filter(pk=int(client_id), is_active=True).first()
    except (TypeError, ValueError):
        return None


def _resolve_reference_and_project(request):
    """Projet optionnel + client optionnel + référence (auto = nom projet ou client)."""
    project = _resolve_project(request.POST.get('project_id'))
    client = _resolve_client(request.POST.get('client_id'))
    command_reference = request.POST.get('command_reference', '').strip()
    if not command_reference:
        if project:
            command_reference = project.name
        elif client:
            command_reference = client.name
    return project, client, command_reference


def _project_margins(start, end):
    """Marge = entrées − sorties, regroupée par projet lié."""
    income_rows = {
        row['project_id']: row
        for row in (
            FinanceIncome.objects.filter(
                income_date__gte=start,
                income_date__lte=end,
                project_id__isnull=False,
            )
            .values('project_id', 'project__name', 'project__status')
            .annotate(total=Sum('amount'), count=Count('id'))
        )
    }
    expense_rows = {
        row['project_id']: row
        for row in (
            FinanceExpense.objects.filter(
                expense_date__gte=start,
                expense_date__lte=end,
                project_id__isnull=False,
            )
            .values('project_id', 'project__name', 'project__status')
            .annotate(total=Sum('amount'), count=Count('id'))
        )
    }
    project_ids = set(income_rows) | set(expense_rows)
    margins = []
    for project_id in project_ids:
        in_row = income_rows.get(project_id, {})
        out_row = expense_rows.get(project_id, {})
        entrees = in_row.get('total') or Decimal('0.00')
        sorties = out_row.get('total') or Decimal('0.00')
        marge = entrees - sorties
        name = in_row.get('project__name') or out_row.get('project__name') or f'Projet #{project_id}'
        status = in_row.get('project__status') or out_row.get('project__status') or ''
        margins.append({
            'project_id': project_id,
            'name': name,
            'status': status,
            'entrees': entrees,
            'sorties': sorties,
            'marge': marge,
            'marge_abs': abs(marge),
            'is_gain': marge >= 0,
            'income_count': in_row.get('count') or 0,
            'expense_count': out_row.get('count') or 0,
        })
    margins.sort(key=lambda row: (-float(row['marge']), row['name'].lower()))
    return margins


def _create_finance_record(request, record_type):
    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    project, client, command_reference = _resolve_reference_and_project(request)
    label = request.POST.get('label', '').strip()
    notes = request.POST.get('notes', '').strip()
    amount_raw = request.POST.get('amount', '').strip().replace(',', '.')
    category = request.POST.get('category', '').strip()
    payment_method = request.POST.get('payment_method', '').strip()

    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide.")
        return redirect('finance_dashboard')

    if not _finance_write_guard(request, parsed_date):
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if not command_reference or not label or not amount_raw:
        messages.error(
            request,
            "Projet, client ou référence, libellé et montant sont obligatoires.",
        )
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    try:
        amount = Decimal(amount_raw)
    except Exception:
        messages.error(request, "Montant invalide.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    attachment, attachment_error = _resolve_attachment(request)
    if attachment_error:
        messages.error(request, attachment_error)
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    payment_method = _valid_choice(payment_method, PAYMENT_METHOD_CHOICES, 'cash')

    common = {
        'created_by': request.user,
        'project': project,
        'client': client,
        'command_reference': command_reference,
        'label': label,
        'payment_method': payment_method,
        'amount': amount,
        'notes': notes,
    }
    if attachment:
        common['attachment'] = attachment

    if record_type == 'income':
        category = _valid_choice(category, INCOME_CATEGORY_CHOICES, 'autre')
        FinanceIncome.objects.create(
            income_date=parsed_date,
            category=category,
            **common,
        )
        messages.success(request, "Encaissement enregistré.")
    else:
        category = _valid_choice(category, EXPENSE_CATEGORY_CHOICES, 'autre')
        FinanceExpense.objects.create(
            expense_date=parsed_date,
            category=category,
            **common,
        )
        messages.success(request, "Dépense enregistrée.")

    return redirect(f"{request.path}?date={parsed_date.isoformat()}")


def _update_finance_record(request, record_type):
    record_id = request.POST.get('record_id', '').strip()
    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    project, client, command_reference = _resolve_reference_and_project(request)
    label = request.POST.get('label', '').strip()
    notes = request.POST.get('notes', '').strip()
    amount_raw = request.POST.get('amount', '').strip().replace(',', '.')
    category = request.POST.get('category', '').strip()
    payment_method = request.POST.get('payment_method', '').strip()

    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide.")
        return redirect('finance_dashboard')

    if not _finance_write_guard(request, parsed_date):
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if not record_id or not command_reference or not label or not amount_raw:
        messages.error(request, "Champs incomplets pour la modification.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    try:
        amount = Decimal(amount_raw)
    except Exception:
        messages.error(request, "Date ou montant invalide.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    model = FinanceIncome if record_type == 'income' else FinanceExpense
    record = model.objects.filter(id=record_id).first()
    if not record:
        messages.error(request, "Enregistrement introuvable.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    # Empêcher aussi la modification d'une écriture dont la date d'origine est clôturée
    original_date = record.income_date if record_type == 'income' else record.expense_date
    if original_date != parsed_date and _is_finance_day_closed(original_date):
        messages.error(
            request,
            "La journée d'origine de cet enregistrement est clôturée.",
        )
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if record_type == 'income':
        record.income_date = parsed_date
        record.category = _valid_choice(category, INCOME_CATEGORY_CHOICES, record.category or 'autre')
    else:
        record.expense_date = parsed_date
        record.category = _valid_choice(category, EXPENSE_CATEGORY_CHOICES, record.category or 'autre')
    record.project = project
    record.client = client
    record.command_reference = command_reference
    record.label = label
    record.notes = notes
    record.amount = amount
    record.payment_method = _valid_choice(
        payment_method, PAYMENT_METHOD_CHOICES, record.payment_method or 'cash'
    )
    record.save()
    messages.success(request, "Enregistrement modifié.")
    return redirect(f"{request.path}?date={parsed_date.isoformat()}")


def _delete_finance_record(request, record_type):
    record_id = request.POST.get('record_id', '').strip()
    selected_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    model = FinanceIncome if record_type == 'income' else FinanceExpense
    record = model.objects.filter(id=record_id).first()
    if not record:
        messages.error(request, "Enregistrement introuvable.")
        return redirect('finance_dashboard')

    record_day = record.income_date if record_type == 'income' else record.expense_date
    if not _finance_write_guard(request, record_day):
        return redirect(f"{request.path}?date={selected_date}")

    record.delete()
    messages.success(request, "Enregistrement annulé.")
    return redirect(f"{request.path}?date={selected_date}")


def _close_finance_day(request):
    from datetime import datetime

    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide.")
        return redirect('finance_dashboard')

    if not can_manage_finance_closure(request.user):
        messages.error(request, "Vous n'avez pas le droit de clôturer la caisse.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    if _is_finance_day_closed(parsed_date):
        messages.info(request, "Cette journée est déjà clôturée.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    FinanceDayClosure.objects.create(
        closure_date=parsed_date,
        closed_by=request.user,
        notes=request.POST.get('notes', '').strip()[:255],
    )
    messages.success(request, f"Journée du {parsed_date.strftime('%d/%m/%Y')} clôturée.")
    return redirect(f"{request.path}?date={parsed_date.isoformat()}")


def _reopen_finance_day(request):
    from datetime import datetime

    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide.")
        return redirect('finance_dashboard')

    if not can_manage_finance_closure(request.user):
        messages.error(request, "Vous n'avez pas le droit de rouvrir la caisse.")
        return redirect(f"{request.path}?date={parsed_date.isoformat()}")

    deleted, _ = FinanceDayClosure.objects.filter(closure_date=parsed_date).delete()
    if deleted:
        messages.success(request, f"Journée du {parsed_date.strftime('%d/%m/%Y')} rouverte.")
    else:
        messages.info(request, "Cette journée n'était pas clôturée.")
    return redirect(f"{request.path}?date={parsed_date.isoformat()}")


@login_required(login_url='login')
def reports_list(request):
    reports = DailyReport.objects.select_related('user').order_by('-date', '-created_at')
    is_management = is_management_user(request.user)

    if not is_management:
        reports = reports.filter(user=request.user)
    else:
        selected_user = request.GET.get('user_id', '').strip()
        if selected_user:
            reports = reports.filter(user_id=selected_user)

    if request.method == 'POST':
        if is_management:
            messages.error(request, "La direction consulte les rapports, les agents les soumettent.")
            return redirect('reports_list')

        department = request.POST.get('department', '').strip()
        project = request.POST.get('project', '').strip()
        team_agent = request.POST.get('team_agent', '').strip()
        observations = request.POST.get('observations', '').strip()

        conception_brief_received = 'conception_brief_received' in request.POST
        conception_croquis_validated = 'conception_croquis_validated' in request.POST
        conception_modeling_done = 'conception_modeling_done' in request.POST
        conception_file_ready = 'conception_file_ready' in request.POST

        decoupe_bois_decoupe = 'decoupe_bois_decoupe' in request.POST
        decoupe_metal_decoupe = 'decoupe_metal_decoupe' in request.POST
        decoupe_pvc_decoupe = 'decoupe_pvc_decoupe' in request.POST
        decoupe_dimensions_verified = 'decoupe_dimensions_verified' in request.POST

        assemblage_method = request.POST.get('assemblage_method', '').strip()
        assemblage_partial = 'assemblage_partial' in request.POST
        assemblage_complete = 'assemblage_complete' in request.POST
        assemblage_renforts = 'assemblage_renforts' in request.POST

        led_bande_posee = 'led_bande_posee' in request.POST
        led_alimentation_installee = 'led_alimentation_installee' in request.POST
        led_test_allumage = 'led_test_allumage' in request.POST
        led_cablage_secure = 'led_cablage_secure' in request.POST

        qualite_alignement = 'qualite_alignement' in request.POST
        qualite_solidite = 'qualite_solidite' in request.POST
        qualite_finitions = 'qualite_finitions' in request.POST
        qualite_conformite = 'qualite_conformite' in request.POST
        qualite_validation = 'qualite_validation' in request.POST

        peinture_poncage = 'peinture_poncage' in request.POST
        peinture_sous_couche = 'peinture_sous_couche' in request.POST
        peinture_peinture = 'peinture_peinture' in request.POST
        peinture_vernis = 'peinture_vernis' in request.POST
        peinture_nettoyage = 'peinture_nettoyage' in request.POST

        livraison_emballage = 'livraison_emballage' in request.POST
        livraison_transport = 'livraison_transport' in request.POST
        livraison_installation = 'livraison_installation' in request.POST
        livraison_rapport_photo = 'livraison_rapport_photo' in request.POST
        livraison_projet_cloture = 'livraison_projet_cloture' in request.POST

        work_done = request.POST.get('work_done', '').strip()
        problems = request.POST.get('problems', '').strip()
        objectives = request.POST.get('objectives', '').strip()
        report_date = request.POST.get('date', '').strip() or str(timezone.localdate())

        if not project:
            messages.error(request, "Le champ 'Projet' est obligatoire.")
            return redirect('reports_list')

        DailyReport.objects.create(
            user=request.user,
            date=report_date,
            department=department,
            project=project,
            team_agent=team_agent,
            conception_brief_received=conception_brief_received,
            conception_croquis_validated=conception_croquis_validated,
            conception_modeling_done=conception_modeling_done,
            conception_file_ready=conception_file_ready,
            decoupe_bois_decoupe=decoupe_bois_decoupe,
            decoupe_metal_decoupe=decoupe_metal_decoupe,
            decoupe_pvc_decoupe=decoupe_pvc_decoupe,
            decoupe_dimensions_verified=decoupe_dimensions_verified,
            assemblage_method=assemblage_method,
            assemblage_partial=assemblage_partial,
            assemblage_complete=assemblage_complete,
            assemblage_renforts=assemblage_renforts,
            led_bande_posee=led_bande_posee,
            led_alimentation_installee=led_alimentation_installee,
            led_test_allumage=led_test_allumage,
            led_cablage_secure=led_cablage_secure,
            qualite_alignement=qualite_alignement,
            qualite_solidite=qualite_solidite,
            qualite_finitions=qualite_finitions,
            qualite_conformite=qualite_conformite,
            qualite_validation=qualite_validation,
            peinture_poncage=peinture_poncage,
            peinture_sous_couche=peinture_sous_couche,
            peinture_peinture=peinture_peinture,
            peinture_vernis=peinture_vernis,
            peinture_nettoyage=peinture_nettoyage,
            livraison_emballage=livraison_emballage,
            livraison_transport=livraison_transport,
            livraison_installation=livraison_installation,
            livraison_rapport_photo=livraison_rapport_photo,
            livraison_projet_cloture=livraison_projet_cloture,
            observations=observations,
            work_done=work_done,
            problems=problems,
            objectives=objectives,
        )
        messages.success(request, "Rapport enregistré avec succès.")
        return redirect('reports_list')

    reports_list = list(reports)
    context = {
        'reports': reports_list,
        'reports_by_month': (
            _group_reports_by_month_then_day(reports_list) if is_management
            else _group_reports_by_month(reports_list)
        ),
        'reports_total': len(reports_list),
        'default_date': timezone.localdate(),
        'is_admin': is_admin_user(request.user),
        'is_management': is_management,
        'agents': User.objects.filter(role='agent').order_by('username') if is_management else [],
        'selected_user': request.GET.get('user_id', '').strip() if is_management else '',
        'can_create_report': not is_management,
        'branch_choices': TECH_BRANCH_CHOICES,
    }
    return render(request, 'reports.html', context)


def _can_view_report(user, report):
    if is_management_user(user) or is_admin_user(user):
        return True
    return report.user_id == user.id


@login_required(login_url='login')
def report_pdf(request, report_id):
    report = get_object_or_404(DailyReport.objects.select_related('user'), id=report_id)
    if not _can_view_report(request.user, report):
        return HttpResponseForbidden('Accès refusé')

    pdf_bytes = build_report_pdf(report)
    filename = f"rapport_{report.date.strftime('%Y%m%d')}_{report.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
def report_a4_view(request, report_id):
    report = get_object_or_404(DailyReport.objects.select_related('user'), id=report_id)
    if not _can_view_report(request.user, report):
        return HttpResponseForbidden('Accès refusé')
    return render(request, 'report_a4.html', {
        'report': report,
    })


@login_required(login_url='login')
def finance_dashboard(request):
    if not _finance_access_or_redirect(request):
        return redirect('dashboard')

    selected_date_str = request.GET.get('date', '').strip() or str(timezone.localdate())
    selected_date = _parse_selected_date(selected_date_str)
    is_today = selected_date == timezone.localdate()
    can_write = can_edit_finance(request.user)
    can_close = can_manage_finance_closure(request.user)
    day_closure = _get_finance_day_closure(selected_date)
    day_is_closed = day_closure is not None
    can_mutate = can_write and not day_is_closed

    filter_category = request.GET.get('filter_category', '').strip()
    filter_project = request.GET.get('filter_project', '').strip()
    filter_client = request.GET.get('filter_client', '').strip()
    filter_payment = request.GET.get('filter_payment', '').strip()

    if request.method == 'POST':
        action = request.POST.get('action', 'create').strip() or 'create'
        if action == 'close_day':
            return _close_finance_day(request)
        if action == 'reopen_day':
            return _reopen_finance_day(request)
        record_type = request.POST.get('record_type', 'expense')
        if action == 'delete':
            return _delete_finance_record(request, record_type)
        if action == 'update':
            return _update_finance_record(request, record_type)
        return _create_finance_record(request, record_type)

    expenses_qs = FinanceExpense.objects.filter(expense_date=selected_date).select_related(
        'created_by', 'project', 'client'
    )
    incomes_qs = FinanceIncome.objects.filter(income_date=selected_date).select_related(
        'created_by', 'project', 'client'
    )
    expenses_qs = _apply_finance_list_filters(
        expenses_qs,
        filter_category=filter_category,
        filter_project=filter_project,
        filter_client=filter_client,
        filter_payment=filter_payment,
    )
    incomes_qs = _apply_finance_list_filters(
        incomes_qs,
        filter_category=filter_category,
        filter_project=filter_project,
        filter_client=filter_client,
        filter_payment=filter_payment,
    )

    daily_expenses = list(expenses_qs.order_by('-created_at'))
    daily_incomes = list(incomes_qs.order_by('-created_at'))
    daily_totals = _finance_totals_for_date(selected_date)

    bounds = _period_bounds(selected_date)
    monthly_totals = _finance_totals(*bounds['monthly'])
    semestrial_totals = _finance_totals(*bounds['semestrial'])
    annual_totals = _finance_totals(*bounds['annual'])
    daily_project_margins = _project_margins(*bounds['daily'])
    monthly_project_margins = _project_margins(*bounds['monthly'])
    monthly_income_categories = _category_totals(
        FinanceIncome, 'income_date', *bounds['monthly'], INCOME_CATEGORY_CHOICES
    )
    monthly_expense_categories = _category_totals(
        FinanceExpense, 'expense_date', *bounds['monthly'], EXPENSE_CATEGORY_CHOICES
    )
    annual_income_categories = _category_totals(
        FinanceIncome, 'income_date', *bounds['annual'], INCOME_CATEGORY_CHOICES
    )
    annual_expense_categories = _category_totals(
        FinanceExpense, 'expense_date', *bounds['annual'], EXPENSE_CATEGORY_CHOICES
    )
    daily_payment_totals = _payment_method_totals(*bounds['daily'])
    monthly_payment_totals = _payment_method_totals(*bounds['monthly'])

    by_command_incomes = (
        incomes_qs.filter(project_id__isnull=True)
        .values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )
    by_command_expenses = (
        expenses_qs.filter(project_id__isnull=True)
        .values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )

    finance_projects = list(
        Project.objects.exclude(status='done').order_by('name', 'id')
    )
    finance_projects_done = list(
        Project.objects.filter(status='done').order_by('-created_at', 'name')[:30]
    )
    finance_clients = list(
        FinanceClient.objects.filter(is_active=True).order_by('name', 'id')
    )

    chart_data = {
        'labels': ['Journalier', 'Mensuel', 'Semestriel', 'Annuel'],
        'entrees': [
            float(daily_totals['entrees']),
            float(monthly_totals['entrees']),
            float(semestrial_totals['entrees']),
            float(annual_totals['entrees']),
        ],
        'sorties': [
            float(daily_totals['sorties']),
            float(monthly_totals['sorties']),
            float(semestrial_totals['sorties']),
            float(annual_totals['sorties']),
        ],
        'soldes': [
            float(daily_totals['solde']),
            float(monthly_totals['solde']),
            float(semestrial_totals['solde']),
            float(annual_totals['solde']),
        ],
    }

    expense_days = {
        row['expense_date']: row
        for row in FinanceExpense.objects.values('expense_date').annotate(total=Sum('amount'), count=Count('id'))
    }
    income_days = {
        row['income_date']: row
        for row in FinanceIncome.objects.values('income_date').annotate(total=Sum('amount'), count=Count('id'))
    }
    all_dates = sorted(set(expense_days) | set(income_days), reverse=True)[:10]
    recent_daily_totals = []
    for day in all_dates:
        out_total = expense_days.get(day, {}).get('total') or Decimal('0.00')
        in_total = income_days.get(day, {}).get('total') or Decimal('0.00')
        solde = in_total - out_total
        recent_daily_totals.append({
            'date': day,
            'entrees': in_total,
            'sorties': out_total,
            'solde': solde,
            'is_gain': solde >= 0,
        })

    # Combined category choices for the day filter (income + expense labels)
    filter_category_choices = list(dict.fromkeys(
        list(INCOME_CATEGORY_CHOICES) + list(EXPENSE_CATEGORY_CHOICES)
    ))

    context = {
        'selected_date': selected_date_str,
        'is_today': is_today,
        'daily_expenses': daily_expenses,
        'daily_incomes': daily_incomes,
        'daily_totals': daily_totals,
        'monthly_totals': monthly_totals,
        'semestrial_totals': semestrial_totals,
        'semester_label': bounds['semester_label'],
        'annual_totals': annual_totals,
        'annual_year': selected_date.year,
        'by_command_incomes': by_command_incomes,
        'by_command_expenses': by_command_expenses,
        'daily_project_margins': daily_project_margins,
        'monthly_project_margins': monthly_project_margins,
        'monthly_income_categories': monthly_income_categories,
        'monthly_expense_categories': monthly_expense_categories,
        'annual_income_categories': annual_income_categories,
        'annual_expense_categories': annual_expense_categories,
        'daily_payment_totals': daily_payment_totals,
        'monthly_payment_totals': monthly_payment_totals,
        'finance_projects': finance_projects,
        'finance_projects_done': finance_projects_done,
        'finance_clients': finance_clients,
        'finance_section': 'caisse',
        'chart_data': chart_data,
        'recent_daily_totals': recent_daily_totals,
        'is_admin': is_admin_user(request.user),
        'is_management': is_management_user(request.user),
        'is_finance': True,
        'can_edit_finance': can_write,
        'can_manage_finance_closure': can_close,
        'can_mutate_finance': can_mutate,
        'day_is_closed': day_is_closed,
        'day_closure': day_closure,
        'income_category_choices': INCOME_CATEGORY_CHOICES,
        'expense_category_choices': EXPENSE_CATEGORY_CHOICES,
        'payment_method_choices': PAYMENT_METHOD_CHOICES,
        'filter_category': filter_category,
        'filter_project': filter_project,
        'filter_client': filter_client,
        'filter_payment': filter_payment,
        'filter_category_choices': filter_category_choices,
    }
    return render(request, 'finance.html', context)


def _finance_period_payload(selected_date, period):
    bounds = _period_bounds(selected_date)
    if period == 'daily':
        start, end = bounds['daily']
        label = f'Journalier — {selected_date.strftime("%d/%m/%Y")}'
        slug = selected_date.strftime('%Y%m%d')
    elif period == 'monthly':
        start, end = bounds['monthly']
        label = f'Mensuel — {selected_date.strftime("%m/%Y")}'
        slug = selected_date.strftime('%Y%m')
    elif period == 'semestrial':
        start, end = bounds['semestrial']
        label = bounds['semester_label']
        slug = f"{selected_date.year}_S{'1' if selected_date.month <= 6 else '2'}"
    elif period == 'annual':
        start, end = bounds['annual']
        label = f'Annuel — {selected_date.year}'
        slug = str(selected_date.year)
    else:
        return None

    incomes = list(
        FinanceIncome.objects.filter(income_date__gte=start, income_date__lte=end)
        .select_related('created_by', 'project', 'client')
        .order_by('income_date', 'id')
    )
    expenses = list(
        FinanceExpense.objects.filter(expense_date__gte=start, expense_date__lte=end)
        .select_related('created_by', 'project', 'client')
        .order_by('expense_date', 'id')
    )
    totals = _finance_totals(start, end)
    project_margins = _project_margins(start, end)
    by_command_incomes = list(
        FinanceIncome.objects.filter(income_date__gte=start, income_date__lte=end)
        .values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )
    by_command_expenses = list(
        FinanceExpense.objects.filter(expense_date__gte=start, expense_date__lte=end)
        .values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )
    return {
        'period': period,
        'period_label': label,
        'slug': slug,
        'start': start,
        'end': end,
        'totals': totals,
        'incomes': incomes,
        'expenses': expenses,
        'project_margins': project_margins,
        'by_command_incomes': by_command_incomes,
        'by_command_expenses': by_command_expenses,
    }


@login_required(login_url='login')
def finance_pdf(request, period):
    if not _finance_access_or_redirect(request):
        return redirect('dashboard')

    selected_date = _parse_selected_date(request.GET.get('date', '').strip())
    payload = _finance_period_payload(selected_date, period)
    if not payload:
        return HttpResponseForbidden('Période invalide')

    pdf_bytes = build_finance_pdf(
        period_label=payload['period_label'],
        start=payload['start'],
        end=payload['end'],
        totals=payload['totals'],
        incomes=payload['incomes'],
        expenses=payload['expenses'],
        by_command_incomes=payload['by_command_incomes'],
        by_command_expenses=payload['by_command_expenses'],
        project_margins=payload.get('project_margins'),
    )
    filename = f"finance_{period}_{payload['slug']}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
def finance_a4_view(request, period):
    if not _finance_access_or_redirect(request):
        return redirect('dashboard')

    selected_date = _parse_selected_date(request.GET.get('date', '').strip())
    payload = _finance_period_payload(selected_date, period)
    if not payload:
        return HttpResponseForbidden('Période invalide')

    return render(request, 'finance_a4.html', {
        **payload,
        'selected_date': selected_date.isoformat(),
    })


@login_required(login_url='login')
def finance_export_excel(request, period):
    """Export CSV UTF-8-SIG (ouvre correctement dans Excel)."""
    if not can_access_finance(request.user):
        messages.error(request, "Accès réservé à l'équipe Finance et à la direction.")
        return redirect('dashboard')

    selected_date = _parse_selected_date(request.GET.get('date', '').strip())
    payload = _finance_period_payload(selected_date, period)
    if not payload:
        return HttpResponseForbidden('Période invalide')

    filename = f"finance_{period}_{payload['slug']}.csv"
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # BOM UTF-8-SIG pour Excel

    writer = csv.writer(response)
    writer.writerow([
        'type', 'date', 'project', 'client', 'reference', 'label',
        'category', 'payment_method', 'amount', 'notes', 'author',
    ])

    def _author_name(user):
        if not user:
            return ''
        if hasattr(user, 'get_display_name'):
            return user.get_display_name()
        return str(user)

    for income in payload['incomes']:
        writer.writerow([
            'income',
            income.income_date.isoformat(),
            income.project.name if income.project_id else '',
            income.client.name if income.client_id else '',
            income.command_reference,
            income.label,
            income.get_category_display(),
            income.get_payment_method_display(),
            str(income.amount),
            income.notes or '',
            _author_name(income.created_by),
        ])
    for expense in payload['expenses']:
        writer.writerow([
            'expense',
            expense.expense_date.isoformat(),
            expense.project.name if expense.project_id else '',
            expense.client.name if expense.client_id else '',
            expense.command_reference,
            expense.label,
            expense.get_category_display(),
            expense.get_payment_method_display(),
            str(expense.amount),
            expense.notes or '',
            _author_name(expense.created_by),
        ])
    return response


def _client_form_payload(request):
    next_action_date_raw = request.POST.get('next_action_date', '').strip()
    next_action_date = None
    if next_action_date_raw:
        try:
            next_action_date = datetime.strptime(next_action_date_raw, '%Y-%m-%d').date()
        except ValueError:
            next_action_date = None

    status = _valid_choice(
        request.POST.get('status', '').strip(),
        CLIENT_STATUS_CHOICES,
        'prospect',
    )
    return {
        'name': request.POST.get('name', '').strip(),
        'contact_name': request.POST.get('contact_name', '').strip(),
        'phone': request.POST.get('phone', '').strip(),
        'email': request.POST.get('email', '').strip(),
        'address': request.POST.get('address', '').strip(),
        'city': request.POST.get('city', '').strip(),
        'country': request.POST.get('country', '').strip() or 'RDC',
        'tax_id': request.POST.get('tax_id', '').strip(),
        'notes': request.POST.get('notes', '').strip(),
        'status': status,
        'next_action': request.POST.get('next_action', '').strip(),
        'next_action_date': next_action_date,
    }


def _commercial_agents_queryset():
    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(org_group='commercial')
            | Q(username__in=['michelle.bukebo', 'michael.kabale'])
        )
        .order_by('first_name', 'last_name', 'username')
    )


def _resolve_commercial_owner(request, *, default_owner=None):
    """Owner forcé pour agent ; libre pour lead/direction/finance."""
    if can_reassign_crm_client(request.user) or can_access_finance(request.user):
        owner_id = request.POST.get('commercial_owner_id', '').strip()
        if owner_id:
            try:
                owner = User.objects.filter(pk=int(owner_id), is_active=True).first()
                if owner:
                    return owner
            except (TypeError, ValueError):
                pass
        return default_owner or request.user
    return request.user


def _crm_clients_queryset(user, *, show_archived=False, owner_filter=None):
    qs = FinanceClient.objects.select_related(
        'created_by', 'commercial_owner'
    ).order_by('name', 'id')
    if show_archived:
        qs = qs.filter(is_active=False)
    else:
        qs = qs.filter(is_active=True)

    if owner_filter:
        qs = qs.filter(commercial_owner_id=owner_filter)
    elif not can_view_all_crm_clients(user):
        qs = qs.filter(commercial_owner=user)
    return qs


def _client_financial_snapshot(client):
    """Montants séparés par projet ; totaux client = somme des projets."""
    projects = list(
        Project.objects.filter(client_id=client.id)
        .order_by('-created_at', '-id')
    )
    project_rows = []
    total_contract = Decimal('0.00')
    total_paid = Decimal('0.00')
    for project in projects:
        contract = project.contract_amount or Decimal('0.00')
        project_paid = (
            FinanceIncome.objects.filter(project_id=project.id).aggregate(total=Sum('amount'))['total']
            or Decimal('0.00')
        )
        remaining = contract - project_paid
        project_rows.append({
            'project': project,
            'contract': contract,
            'paid': project_paid,
            'remaining': remaining,
        })
        total_contract += contract
        total_paid += project_paid

    remaining = total_contract - total_paid
    return {
        'projects': project_rows,
        'project_count': len(projects),
        'total_contract': total_contract,
        'paid': total_paid,
        'remaining': remaining,
        'is_settled': remaining <= 0 and total_contract > 0,
    }


def _find_duplicate_client(*, name, phone='', exclude_id=None):
    """Détecte une fiche active déjà existante (même nom, ou même téléphone)."""
    name = (name or '').strip()
    phone = (phone or '').strip()
    qs = FinanceClient.objects.filter(is_active=True)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    if name:
        by_name = qs.filter(name__iexact=name).select_related('commercial_owner').first()
        if by_name:
            return by_name

    if phone and len(phone) >= 6:
        by_phone = qs.filter(phone__iexact=phone).select_related('commercial_owner').first()
        if by_phone:
            return by_phone
    return None


def _build_clients_with_finance(clients):
    rows = []
    for client in clients:
        snap = _client_financial_snapshot(client)
        rows.append({
            'client': client,
            **snap,
        })
    return rows


def _create_crm_project_for_client(request, client):
    """Ajoute un projet sur un client existant (même fiche client)."""
    from projects.views import _default_technical_director, _default_project_manager

    name = request.POST.get('project_name', '').strip()
    description = request.POST.get('project_description', '').strip() or f'Projet pour {client.name}'
    start_date = request.POST.get('project_start_date', '').strip() or str(timezone.localdate())
    end_date = request.POST.get('project_end_date', '').strip() or str(timezone.localdate())
    amount_raw = request.POST.get('project_amount', '').strip().replace(',', '.')
    branch = request.POST.get('project_branch', 'metal_design').strip() or 'metal_design'

    if not name:
        return None, "Le nom du projet est obligatoire."

    try:
        amount = Decimal(amount_raw) if amount_raw else Decimal('0.00')
        if amount < 0:
            amount = Decimal('0.00')
    except Exception:
        return None, "Montant du projet invalide."

    try:
        parsed_start = datetime.strptime(start_date, '%Y-%m-%d').date()
        parsed_end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        return None, "Dates du projet invalides."

    commercial = client.commercial_owner or request.user
    manager = _default_project_manager() or request.user
    technical_director = _default_technical_director()

    project = Project.objects.create(
        name=name,
        description=description,
        start_date=parsed_start,
        end_date=parsed_end,
        status='pending',
        branch=branch,
        manager=manager,
        technical_director=technical_director,
        commercial_agent=commercial,
        client=client,
        contract_amount=amount,
    )
    members = [m for m in (commercial, manager, technical_director) if m]
    project.members.set(members)
    return project, None


def _crm_followup_agenda(user, *, owner_filter=None):
    """Relances en retard et à faire aujourd'hui."""
    today = timezone.localdate()
    qs = _crm_clients_queryset(
        user, show_archived=False, owner_filter=owner_filter
    ).exclude(next_action_date__isnull=True)
    overdue = list(
        qs.filter(next_action_date__lt=today)
        .select_related('commercial_owner')
        .order_by('next_action_date', 'name')[:40]
    )
    due_today = list(
        qs.filter(next_action_date=today)
        .select_related('commercial_owner')
        .order_by('name')[:40]
    )
    return overdue, due_today


def _merge_crm_clients(keep, absorb):
    """Fusionne absorb dans keep : projets, paiements, suivis ; archive absorb."""
    if not keep or not absorb:
        return False, "Clients introuvables."
    if keep.id == absorb.id:
        return False, "Impossible de fusionner un client avec lui-même."

    Project.objects.filter(client_id=absorb.id).update(client_id=keep.id)
    FinanceIncome.objects.filter(client_id=absorb.id).update(client_id=keep.id)
    FinanceExpense.objects.filter(client_id=absorb.id).update(client_id=keep.id)
    CrmFollowUp.objects.filter(client_id=absorb.id).update(client_id=keep.id)

    for field in ('phone', 'email', 'address', 'city', 'contact_name', 'tax_id', 'country'):
        if not (getattr(keep, field) or '').strip() and (getattr(absorb, field) or '').strip():
            setattr(keep, field, getattr(absorb, field))

    if not keep.next_action and absorb.next_action:
        keep.next_action = absorb.next_action
        keep.next_action_date = absorb.next_action_date
    elif keep.next_action_date and absorb.next_action_date:
        if absorb.next_action_date < keep.next_action_date:
            keep.next_action = absorb.next_action
            keep.next_action_date = absorb.next_action_date

    note_block = (
        f"\n\n[Fusion {timezone.localdate().isoformat()}] "
        f"Fiche « {absorb.name} » (#{absorb.id}) fusionnée ici."
    )
    if absorb.notes:
        note_block += f"\nNotes reprises : {absorb.notes}"
    keep.notes = (keep.notes or '') + note_block
    keep.save()

    absorb.is_active = False
    absorb.notes = (
        (absorb.notes or '')
        + f"\n[Fusionné dans « {keep.name} » #{keep.id} le {timezone.localdate().isoformat()}]"
    )
    absorb.save(update_fields=['is_active', 'notes', 'updated_at'])
    return True, None


def _record_crm_project_payment(request, client):
    """Enregistre un encaissement lié à un projet précis du client."""
    try:
        project_id = int(request.POST.get('project_id', '').strip() or 0)
    except (TypeError, ValueError):
        project_id = 0
    project = Project.objects.filter(id=project_id, client_id=client.id).first()
    if not project:
        return None, "Sélectionnez un projet appartenant à ce client."

    amount_raw = request.POST.get('amount', '').strip().replace(',', '.')
    try:
        amount = Decimal(amount_raw)
    except Exception:
        return None, "Montant invalide."
    if amount <= 0:
        return None, "Le montant doit être supérieur à 0."

    date_raw = request.POST.get('income_date', '').strip() or str(timezone.localdate())
    try:
        income_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        return None, "Date d'encaissement invalide."

    category = _valid_choice(
        request.POST.get('category', '').strip(),
        INCOME_CATEGORY_CHOICES,
        'acompte',
    )
    payment_method = _valid_choice(
        request.POST.get('payment_method', '').strip(),
        PAYMENT_METHOD_CHOICES,
        'cash',
    )
    label = request.POST.get('label', '').strip() or f"Encaissement — {project.name}"
    notes = request.POST.get('notes', '').strip()

    income = FinanceIncome.objects.create(
        created_by=request.user,
        project=project,
        client=client,
        income_date=income_date,
        command_reference=project.name[:120],
        label=label[:180],
        category=category,
        payment_method=payment_method,
        amount=amount,
        notes=notes,
    )
    return income, None


def _crm_query_redirect(request, *, edit_id=None, extra=None):
    """Conserve les filtres CRM dans les redirections."""
    params = request.GET.copy()
    if extra:
        for key, value in extra.items():
            if value is None or value == '':
                params.pop(key, None)
            else:
                params[key] = value
    if edit_id is not None:
        params['edit'] = str(edit_id)
    qs = params.urlencode()
    return f"{request.path}?{qs}" if qs else request.path


@login_required(login_url='login')
def finance_clients(request):
    """CRM clients / portefeuille commercial (même base pour Finance et Commercial)."""
    if not can_access_crm(request.user):
        messages.error(request, "Accès réservé au CRM commercial, à la direction et à la finance.")
        return redirect('dashboard')

    can_write = can_edit_crm_clients(request.user)
    can_reassign = can_reassign_crm_client(request.user) or can_access_finance(request.user)
    view_all = can_view_all_crm_clients(request.user)
    edit_id = request.GET.get('edit', '').strip()
    owner_filter = request.GET.get('owner', '').strip() or None
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    reste_filter = request.GET.get('reste', '').strip() == '1'
    redirect_name = 'crm_portfolio' if request.resolver_match.url_name == 'crm_portfolio' else 'finance_clients'

    if request.method == 'POST':
        if not can_write:
            messages.error(request, "Accès en lecture seule sur les fiches clients.")
            return redirect(redirect_name)

        action = request.POST.get('action', 'create').strip() or 'create'
        if action == 'deactivate':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
            else:
                client.is_active = False
                client.save(update_fields=['is_active', 'updated_at'])
                messages.success(request, f"Client « {client.name} » archivé.")
            return redirect(redirect_name)

        if action == 'reactivate':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
            else:
                client.is_active = True
                client.save(update_fields=['is_active', 'updated_at'])
                messages.success(request, f"Client « {client.name} » réactivé.")
            return redirect(redirect_name)

        if action == 'add_followup':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
                return redirect(redirect_name)
            content = request.POST.get('content', '').strip()
            follow_type = _valid_choice(
                request.POST.get('follow_type', '').strip(),
                CrmFollowUp.TYPE_CHOICES,
                'note',
            )
            if not content:
                messages.error(request, "Le contenu du suivi est obligatoire.")
            else:
                CrmFollowUp.objects.create(
                    client=client,
                    author=request.user,
                    follow_type=follow_type,
                    content=content,
                )
                messages.success(request, "Suivi ajouté.")
            return redirect(_crm_query_redirect(request, edit_id=client.id))

        if action == 'add_project':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
                return redirect(redirect_name)
            project, error = _create_crm_project_for_client(request, client)
            if error:
                messages.error(request, error)
                return redirect(_crm_query_redirect(request, edit_id=client.id))
            messages.success(
                request,
                f"Projet « {project.name} » ajouté au client « {client.name} » "
                f"(montant {project.contract_amount} $ — suivi séparé des autres projets).",
            )
            return redirect(_crm_query_redirect(request, edit_id=client.id))

        if action == 'add_payment':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
                return redirect(redirect_name)
            income, error = _record_crm_project_payment(request, client)
            if error:
                messages.error(request, error)
                return redirect(_crm_query_redirect(request, edit_id=client.id))
            messages.success(
                request,
                f"Encaissement de {income.amount} $ enregistré sur « {income.project.name} ».",
            )
            return redirect(_crm_query_redirect(request, edit_id=client.id))

        if action == 'reassign':
            if not can_reassign:
                messages.error(request, "Vous n’avez pas le droit de réaffecter un client.")
                return redirect(redirect_name)
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
                return redirect(redirect_name)
            new_owner = _resolve_commercial_owner(
                request, default_owner=client.commercial_owner
            )
            if not new_owner:
                messages.error(request, "Choisissez un commercial valide.")
                return redirect(_crm_query_redirect(request, edit_id=client.id))
            old_name = (
                client.commercial_owner.get_display_name()
                if client.commercial_owner_id
                else '—'
            )
            client.commercial_owner = new_owner
            client.save(update_fields=['commercial_owner', 'updated_at'])
            # Aligner l’agent commercial des projets liés
            Project.objects.filter(client_id=client.id).update(commercial_agent=new_owner)
            messages.success(
                request,
                f"Client « {client.name} » affecté à {new_owner.get_display_name()} "
                f"(avant : {old_name}).",
            )
            return redirect(_crm_query_redirect(request))

        if action == 'merge_clients':
            keep = FinanceClient.objects.filter(id=request.POST.get('keep_id')).first()
            absorb = FinanceClient.objects.filter(id=request.POST.get('absorb_id')).first()
            if (
                not keep
                or not absorb
                or not can_edit_crm_client(request.user, keep)
                or not can_edit_crm_client(request.user, absorb)
            ):
                messages.error(request, "Fusion impossible : clients introuvables ou non autorisés.")
                return redirect(redirect_name)
            ok, error = _merge_crm_clients(keep, absorb)
            if not ok:
                messages.error(request, error)
                return redirect(_crm_query_redirect(request, edit_id=keep.id if keep else None))
            messages.success(
                request,
                f"« {absorb.name} » a été fusionné dans « {keep.name} ». "
                f"Projets et paiements conservés sur la fiche principale.",
            )
            return redirect(_crm_query_redirect(request, edit_id=keep.id))

        payload = _client_form_payload(request)
        if not payload['name']:
            messages.error(request, "Le nom / société est obligatoire.")
            return redirect(redirect_name)

        if action == 'update':
            client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
            if not client or not can_edit_crm_client(request.user, client):
                messages.error(request, "Client introuvable ou non autorisé.")
                return redirect(redirect_name)
            duplicate = _find_duplicate_client(
                name=payload['name'],
                phone=payload['phone'],
                exclude_id=client.id,
            )
            if duplicate:
                messages.error(
                    request,
                    f"Un autre client porte déjà ce nom/téléphone : « {duplicate.name} ». "
                    f"Utilisez la fusion de fiches ou ouvrez sa fiche pour ajouter un projet.",
                )
                return redirect(_crm_query_redirect(request, edit_id=duplicate.id))
            for key, value in payload.items():
                setattr(client, key, value)
            client.commercial_owner = _resolve_commercial_owner(
                request, default_owner=client.commercial_owner or request.user
            )
            client.save()
            messages.success(request, "Fiche client mise à jour.")
            return redirect(_crm_query_redirect(request, edit_id=client.id))

        duplicate = _find_duplicate_client(name=payload['name'], phone=payload['phone'])
        if duplicate:
            messages.warning(
                request,
                f"Le client « {duplicate.name} » existe déjà. "
                f"N’ajoutez pas une 2ᵉ fiche : ouvrez-le et ajoutez un nouveau projet "
                f"(ou fusionnez les doublons).",
            )
            return redirect(_crm_query_redirect(request, edit_id=duplicate.id))

        owner = _resolve_commercial_owner(request, default_owner=request.user)
        client = FinanceClient.objects.create(
            created_by=request.user,
            commercial_owner=owner,
            **payload,
        )
        project_name = request.POST.get('project_name', '').strip()
        if project_name:
            project, error = _create_crm_project_for_client(request, client)
            if error:
                messages.warning(
                    request,
                    f"Client créé, mais le projet n’a pas pu être ajouté : {error}",
                )
                return redirect(_crm_query_redirect(request, edit_id=client.id))
            messages.success(
                request,
                f"Client « {client.name} » créé avec le projet « {project.name} » "
                f"({project.contract_amount} $).",
            )
            return redirect(_crm_query_redirect(request, edit_id=client.id))

        messages.success(request, "Client ajouté au portefeuille.")
        return redirect(_crm_query_redirect(request, edit_id=client.id))

    show_archived = request.GET.get('archived') == '1'
    filter_owner_id = None
    if view_all and owner_filter:
        try:
            filter_owner_id = int(owner_filter)
        except (TypeError, ValueError):
            filter_owner_id = None

    if status_filter and status_filter not in {key for key, _ in CLIENT_STATUS_CHOICES}:
        status_filter = ''

    follow_ups_qs = CrmFollowUp.objects.select_related('author').order_by('-created_at')
    clients_qs = _crm_clients_queryset(
        request.user,
        show_archived=show_archived,
        owner_filter=filter_owner_id,
    ).prefetch_related(Prefetch('follow_ups', queryset=follow_ups_qs))

    if search_q:
        clients_qs = clients_qs.filter(
            Q(name__icontains=search_q)
            | Q(phone__icontains=search_q)
            | Q(email__icontains=search_q)
            | Q(contact_name__icontains=search_q)
            | Q(city__icontains=search_q)
        )
    if status_filter:
        clients_qs = clients_qs.filter(status=status_filter)

    clients_list = list(clients_qs)
    clients_with_finance = _build_clients_with_finance(clients_list)
    if reste_filter:
        clients_with_finance = [row for row in clients_with_finance if row['remaining'] > 0]
        clients_list = [row['client'] for row in clients_with_finance]

    edit_client = None
    edit_follow_ups = []
    edit_finance = None
    merge_candidates = []
    if edit_id and can_write:
        candidate = (
            FinanceClient.objects.filter(id=edit_id)
            .select_related('commercial_owner')
            .prefetch_related(Prefetch('follow_ups', queryset=follow_ups_qs))
            .first()
        )
        if candidate and can_edit_crm_client(request.user, candidate):
            edit_client = candidate
            edit_follow_ups = list(candidate.follow_ups.all()[:20])
            edit_finance = _client_financial_snapshot(candidate)
            merge_candidates = [
                c for c in _crm_clients_queryset(request.user, show_archived=False)
                if c.id != candidate.id and can_edit_crm_client(request.user, c)
            ]

    commercial_agents = list(_commercial_agents_queryset()) if (can_reassign or view_all) else []
    active_clients_for_project = list(
        _crm_clients_queryset(request.user, show_archived=False).order_by('name', 'id')
    )

    overdue_clients, due_today_clients = _crm_followup_agenda(
        request.user, owner_filter=filter_owner_id
    )

    visible_active = _crm_clients_queryset(
        request.user,
        show_archived=False,
        owner_filter=filter_owner_id,
    )
    portfolio_count = visible_active.count()

    selected_owner_user = None
    if filter_owner_id:
        selected_owner_user = User.objects.filter(id=filter_owner_id).first()
        my_portfolio_count = FinanceClient.objects.filter(
            is_active=True, commercial_owner_id=filter_owner_id
        ).count()
    else:
        my_portfolio_count = FinanceClient.objects.filter(
            is_active=True, commercial_owner=request.user
        ).count()

    portfolio_total = sum((row['total_contract'] for row in clients_with_finance), Decimal('0.00'))
    portfolio_paid = sum((row['paid'] for row in clients_with_finance), Decimal('0.00'))
    portfolio_remaining = portfolio_total - portfolio_paid

    return render(request, 'finance_clients.html', {
        'clients': clients_list,
        'clients_with_finance': clients_with_finance,
        'active_clients_for_project': active_clients_for_project,
        'edit_client': edit_client,
        'edit_follow_ups': edit_follow_ups,
        'edit_finance': edit_finance,
        'merge_candidates': merge_candidates,
        'followup_type_choices': CrmFollowUp.TYPE_CHOICES,
        'client_status_choices': CLIENT_STATUS_CHOICES,
        'income_category_choices': INCOME_CATEGORY_CHOICES,
        'payment_method_choices': PAYMENT_METHOD_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'show_archived': show_archived,
        'search_q': search_q,
        'status_filter': status_filter,
        'reste_filter': reste_filter,
        'overdue_clients': overdue_clients,
        'due_today_clients': due_today_clients,
        'can_edit_finance': can_write,
        'can_edit_crm': can_write,
        'can_reassign_crm': can_reassign,
        'can_view_all_crm': view_all,
        'is_commercial_lead_user': is_commercial_lead(request.user),
        'commercial_agents': commercial_agents,
        'selected_owner': str(filter_owner_id or ''),
        'selected_owner_user': selected_owner_user,
        'portfolio_count': portfolio_count,
        'my_portfolio_count': my_portfolio_count,
        'portfolio_total': portfolio_total,
        'portfolio_paid': portfolio_paid,
        'portfolio_remaining': portfolio_remaining,
        'is_admin': is_admin_user(request.user),
        'is_management': is_management_user(request.user),
        'is_finance': can_access_finance(request.user),
        'is_crm': True,
        'finance_section': 'clients',
        'crm_mode': request.resolver_match.url_name == 'crm_portfolio',
        'today': timezone.localdate(),
    })
