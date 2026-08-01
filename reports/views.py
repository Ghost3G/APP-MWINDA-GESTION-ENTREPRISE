from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.http import HttpResponse, HttpResponseForbidden

from projects.branches import TECH_BRANCH_CHOICES
from users.permissions import is_admin_user, is_management_user, can_access_finance

from .models import DailyReport, FinanceExpense, FinanceIncome
from .pdf import build_report_pdf, build_finance_pdf

User = get_user_model()


def _finance_access_or_redirect(request):
    can_access = can_access_finance(request.user)
    if not can_access:
        messages.error(request, "Accès réservé au service financier et à la direction.")
        return None
    return can_access


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


def _create_finance_record(request, record_type):
    from datetime import datetime

    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    command_reference = request.POST.get('command_reference', '').strip()
    label = request.POST.get('label', '').strip()
    notes = request.POST.get('notes', '').strip()
    amount_raw = request.POST.get('amount', '').strip().replace(',', '.')

    if not command_reference or not label or not amount_raw:
        messages.error(request, "Commande, libellé et montant sont obligatoires.")
        return redirect('finance_dashboard')

    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Date invalide.")
        return redirect('finance_dashboard')

    try:
        amount = Decimal(amount_raw)
    except Exception:
        messages.error(request, "Montant invalide.")
        return redirect('finance_dashboard')

    if amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect('finance_dashboard')

    if record_type == 'income':
        FinanceIncome.objects.create(
            created_by=request.user,
            income_date=parsed_date,
            command_reference=command_reference,
            label=label,
            amount=amount,
            notes=notes,
        )
        messages.success(request, "Encaissement enregistré.")
    else:
        FinanceExpense.objects.create(
            created_by=request.user,
            expense_date=parsed_date,
            command_reference=command_reference,
            label=label,
            amount=amount,
            notes=notes,
        )
        messages.success(request, "Dépense enregistrée.")

    return redirect(f"{request.path}?date={parsed_date.isoformat()}")


def _update_finance_record(request, record_type):
    from datetime import datetime

    record_id = request.POST.get('record_id', '').strip()
    record_date = request.POST.get('record_date', '').strip() or str(timezone.localdate())
    command_reference = request.POST.get('command_reference', '').strip()
    label = request.POST.get('label', '').strip()
    notes = request.POST.get('notes', '').strip()
    amount_raw = request.POST.get('amount', '').strip().replace(',', '.')

    if not record_id or not command_reference or not label or not amount_raw:
        messages.error(request, "Champs incomplets pour la modification.")
        return redirect('finance_dashboard')

    try:
        parsed_date = datetime.strptime(record_date, '%Y-%m-%d').date()
        amount = Decimal(amount_raw)
    except Exception:
        messages.error(request, "Date ou montant invalide.")
        return redirect('finance_dashboard')

    if amount <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect('finance_dashboard')

    model = FinanceIncome if record_type == 'income' else FinanceExpense
    record = model.objects.filter(id=record_id).first()
    if not record:
        messages.error(request, "Enregistrement introuvable.")
        return redirect('finance_dashboard')

    if record_type == 'income':
        record.income_date = parsed_date
    else:
        record.expense_date = parsed_date
    record.command_reference = command_reference
    record.label = label
    record.notes = notes
    record.amount = amount
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
    record.delete()
    messages.success(request, "Enregistrement annulé.")
    return redirect(f"{request.path}?date={selected_date}")


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

    context = {
        'reports': reports,
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

    if request.method == 'POST':
        record_type = request.POST.get('record_type', 'expense')
        action = request.POST.get('action', 'create').strip() or 'create'
        if action == 'delete':
            return _delete_finance_record(request, record_type)
        if action == 'update':
            return _update_finance_record(request, record_type)
        return _create_finance_record(request, record_type)

    expenses_qs = FinanceExpense.objects.filter(expense_date=selected_date).select_related('created_by')
    incomes_qs = FinanceIncome.objects.filter(income_date=selected_date).select_related('created_by')

    daily_expenses = list(expenses_qs.order_by('-created_at'))
    daily_incomes = list(incomes_qs.order_by('-created_at'))
    daily_totals = _finance_totals_for_date(selected_date)

    bounds = _period_bounds(selected_date)
    monthly_totals = _finance_totals(*bounds['monthly'])
    semestrial_totals = _finance_totals(*bounds['semestrial'])
    annual_totals = _finance_totals(*bounds['annual'])

    by_command_incomes = (
        incomes_qs.values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )
    by_command_expenses = (
        expenses_qs.values('command_reference')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total', 'command_reference')
    )

    chart_data = {
        'labels': ['Journalier', 'Mensuel', 'Semestriel'],
        'entrees': [float(daily_totals['entrees']), float(monthly_totals['entrees']), float(semestrial_totals['entrees'])],
        'sorties': [float(daily_totals['sorties']), float(monthly_totals['sorties']), float(semestrial_totals['sorties'])],
        'soldes': [float(daily_totals['solde']), float(monthly_totals['solde']), float(semestrial_totals['solde'])],
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
        'by_command_incomes': by_command_incomes,
        'by_command_expenses': by_command_expenses,
        'chart_data': chart_data,
        'recent_daily_totals': recent_daily_totals,
        'is_admin': is_admin_user(request.user),
        'is_management': is_management_user(request.user),
        'is_finance': True,
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
    else:
        return None

    incomes = list(
        FinanceIncome.objects.filter(income_date__gte=start, income_date__lte=end)
        .select_related('created_by')
        .order_by('income_date', 'id')
    )
    expenses = list(
        FinanceExpense.objects.filter(expense_date__gte=start, expense_date__lte=end)
        .select_related('created_by')
        .order_by('expense_date', 'id')
    )
    totals = _finance_totals(start, end)
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
