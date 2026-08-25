"""Pages CRM dédiées — navigation par sous-menu (Finance inchangé)."""
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from projects.branches import TECH_BRANCH_CHOICES
from projects.models import Project
from users.permissions import (
    can_access_crm,
    can_create_crm_commercial_report,
    can_edit_crm_client,
    can_edit_crm_clients,
    can_reassign_crm_client,
    can_view_all_crm_clients,
    is_commercial_lead,
)

from .chart_data import crm_dashboard_all_charts
from .models import CrmCommercialReport, CrmFollowUp, FinanceClient, FinanceIncome
from .views import (
    CLIENT_STATUS_CHOICES,
    INCOME_CATEGORY_CHOICES,
    PAYMENT_METHOD_CHOICES,
    _assign_client_code,
    _build_clients_with_finance,
    _client_financial_snapshot,
    _client_form_payload,
    _commercial_agents_queryset,
    _crm_clients_queryset,
    _find_duplicate_client,
    _link_project_to_client,
    _merge_crm_clients,
    _resolve_commercial_owner,
    _valid_choice,
)

User = get_user_model()

CRM_ROUTE_NAMES = frozenset({
    'crm_dashboard',
    'crm_my_clients',
    'crm_portfolio',
    'crm_vente_day',
    'crm_vente_month',
    'crm_vente_year',
    'crm_relance',
    'crm_relance_prospect',
    'crm_relance_recouvrement',
    'crm_new_client',
    'crm_reassign',
    'crm_reports_list',
    'crm_report_detail',
    'crm_report_pdf',
})

CRM_VENTE_PERIODS = {
    'jour': 'Jour',
    'mois': 'Mois',
    'annee': 'Année',
}


def _crm_guard(request):
    if not can_access_crm(request.user):
        messages.error(request, 'Accès CRM réservé aux commerciaux et à la direction.')
        return redirect('dashboard')
    return None


def _crm_redirect(request, *, path=None, **query):
    params = request.GET.copy()
    for key, value in query.items():
        if value is None or value == '':
            params.pop(key, None)
        else:
            params[key] = value
    target = path or request.path
    qs = params.urlencode()
    return redirect(f'{target}?{qs}' if qs else target)


def _crm_prospect_relance(user, *, owner_filter=None, see_all=None):
    today = timezone.localdate()
    qs = _crm_clients_queryset(
        user, show_archived=False, owner_filter=owner_filter, see_all=see_all
    ).filter(status='prospect')
    overdue = list(
        qs.filter(next_action_date__lt=today)
        .select_related('commercial_owner')
        .order_by('next_action_date', 'name')[:50]
    )
    due_today = list(
        qs.filter(next_action_date=today)
        .select_related('commercial_owner')
        .order_by('name')[:50]
    )
    upcoming = list(
        qs.filter(next_action_date__gt=today)
        .select_related('commercial_owner')
        .order_by('next_action_date', 'name')[:30]
    )
    without_date = list(
        qs.filter(next_action_date__isnull=True)
        .select_related('commercial_owner')
        .order_by('name')[:30]
    )
    return overdue, due_today, upcoming, without_date


def _crm_recouvrement_rows(user, *, owner_filter=None, see_all=None):
    clients = list(
        _crm_clients_queryset(
            user, show_archived=False, owner_filter=owner_filter, see_all=see_all
        )
    )
    rows = [row for row in _build_clients_with_finance(clients) if row['remaining'] > 0]
    rows.sort(key=lambda row: (-row['remaining'], row['client'].name.lower()))
    total_remaining = sum((row['remaining'] for row in rows), Decimal('0.00'))
    return rows, total_remaining


def _crm_income_queryset(user, *, see_all, owner_filter=None):
    qs = FinanceIncome.objects.select_related('client', 'project', 'created_by')
    if see_all and owner_filter:
        qs = qs.filter(
            Q(client__commercial_owner_id=owner_filter)
            | Q(project__commercial_agent_id=owner_filter)
        )
    elif not see_all:
        qs = qs.filter(
            Q(client__commercial_owner=user) | Q(project__commercial_agent=user)
        )
    return qs


def _crm_vente_bounds(period, selected_date):
    if period == 'jour':
        return selected_date, selected_date, selected_date.strftime('%d/%m/%Y')
    if period == 'mois':
        last_day = monthrange(selected_date.year, selected_date.month)[1]
        start = selected_date.replace(day=1)
        end = selected_date.replace(day=last_day)
        return start, end, selected_date.strftime('%B %Y')
    start = selected_date.replace(month=1, day=1)
    end = selected_date.replace(month=12, day=31)
    return start, end, str(selected_date.year)


def _crm_reports_for_charts(user, *, see_all):
    today = timezone.localdate()
    start = today - timedelta(days=90)
    qs = CrmCommercialReport.objects.filter(activity_date__gte=start)
    if not see_all:
        qs = qs.filter(author=user)
    return qs.order_by('-activity_date', '-created_at')


def _crm_shared_context(request, *, page_key):
    user = request.user
    can_write = can_edit_crm_clients(user)
    can_reassign = can_reassign_crm_client(user)
    view_all = can_view_all_crm_clients(user)
    owner_filter = request.GET.get('owner', '').strip() or None
    filter_owner_id = None
    if view_all and owner_filter:
        try:
            filter_owner_id = int(owner_filter)
        except (TypeError, ValueError):
            filter_owner_id = None

    follow_ups_qs = CrmFollowUp.objects.select_related('author').order_by('-created_at')
    commercial_agents = list(_commercial_agents_queryset()) if (can_reassign or view_all) else []
    active_clients = list(
        _crm_clients_queryset(user, show_archived=False, see_all=view_all).order_by('name', 'id')
    )
    linkable_projects = list(
        Project.objects.filter(client__isnull=True)
        .select_related('manager', 'commercial_agent')
        .order_by('-created_at', 'name', 'id')[:200]
    )

    selected_owner_user = None
    if filter_owner_id:
        selected_owner_user = User.objects.filter(id=filter_owner_id).first()

    return {
        'crm_page': page_key,
        'can_edit_crm': can_write,
        'can_reassign_crm': can_reassign,
        'can_view_all_crm': view_all,
        'can_create_crm_report': can_create_crm_commercial_report(user),
        'is_commercial_lead_user': is_commercial_lead(user),
        'commercial_agents': commercial_agents,
        'active_clients_for_project': active_clients,
        'linkable_projects': linkable_projects,
        'client_status_choices': CLIENT_STATUS_CHOICES,
        'followup_type_choices': CrmFollowUp.TYPE_CHOICES,
        'branch_choices': TECH_BRANCH_CHOICES,
        'income_category_choices': INCOME_CATEGORY_CHOICES,
        'payment_method_choices': PAYMENT_METHOD_CHOICES,
        'selected_owner': str(filter_owner_id or ''),
        'selected_owner_user': selected_owner_user,
        'filter_owner_id': filter_owner_id,
        'view_all': view_all,
        'follow_ups_qs': follow_ups_qs,
        'today': timezone.localdate(),
    }


def _load_edit_client(request, *, see_all, follow_ups_qs, client_id=None):
    open_id = client_id or request.GET.get('open', '').strip() or request.GET.get('edit', '').strip()
    if not open_id:
        return None, [], [], None, []

    candidate = (
        FinanceClient.objects.filter(id=open_id)
        .select_related('commercial_owner')
        .prefetch_related(Prefetch('follow_ups', queryset=follow_ups_qs))
        .first()
    )
    if not candidate or not can_edit_crm_client(request.user, candidate):
        return None, [], [], None, []

    edit_follow_ups = list(candidate.follow_ups.all()[:20])
    edit_commercial_reports = list(
        CrmCommercialReport.objects.filter(client=candidate)
        .select_related('author')
        .order_by('-activity_date', '-created_at')[:15]
    )
    edit_finance = _client_financial_snapshot(candidate)
    merge_candidates = []
    if can_edit_crm_clients(request.user):
        merge_candidates = [
            c for c in _crm_clients_queryset(request.user, show_archived=False, see_all=see_all)
            if c.id != candidate.id and can_edit_crm_client(request.user, c)
        ]
    return candidate, edit_follow_ups, edit_commercial_reports, edit_finance, merge_candidates


def _handle_crm_post(request, *, default_redirect):
    if request.method != 'POST':
        return None
    if not can_edit_crm_clients(request.user):
        messages.error(request, 'Mode consultation sur les fiches clients.')
        return redirect(default_redirect)

    action = request.POST.get('action', 'create').strip() or 'create'
    can_reassign = can_reassign_crm_client(request.user)
    see_all = can_view_all_crm_clients(request.user)

    if action == 'add_followup':
        client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
        if not client or not can_edit_crm_client(request.user, client):
            messages.error(request, 'Client introuvable ou non autorisé.')
            return redirect(default_redirect)
        content = request.POST.get('content', '').strip()
        follow_type = _valid_choice(
            request.POST.get('follow_type', '').strip(),
            CrmFollowUp.TYPE_CHOICES,
            'note',
        )
        if not content:
            messages.error(request, 'Le contenu du suivi est obligatoire.')
        else:
            CrmFollowUp.objects.create(
                client=client,
                author=request.user,
                follow_type=follow_type,
                content=content,
            )
            messages.success(request, 'Suivi ajouté.')
        return _crm_redirect(request, path=default_redirect, open=str(client.id))

    if action == 'link_project':
        client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
        if not client or not can_edit_crm_client(request.user, client):
            messages.error(request, 'Client introuvable ou non autorisé.')
            return redirect(default_redirect)
        try:
            project_id = int(request.POST.get('project_id', '').strip() or 0)
        except (TypeError, ValueError):
            project_id = 0
        project = Project.objects.filter(id=project_id, client__isnull=True).first()
        if not project:
            messages.error(request, 'Projet introuvable ou déjà lié à un client.')
            return _crm_redirect(request, path=default_redirect, open=str(client.id))
        _link_project_to_client(project, client)
        messages.success(request, f'Projet « {project.name} » lié au client « {client.name} ».')
        return _crm_redirect(request, path=default_redirect, open=str(client.id))

    if action == 'reassign':
        if not can_reassign:
            messages.error(request, 'Vous n’avez pas le droit de réaffecter un client.')
            return redirect(default_redirect)
        client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
        if not client or not can_edit_crm_client(request.user, client):
            messages.error(request, 'Client introuvable ou non autorisé.')
            return redirect(default_redirect)
        new_owner = _resolve_commercial_owner(request, default_owner=client.commercial_owner)
        if not new_owner:
            messages.error(request, 'Choisissez un commercial valide.')
            return redirect(default_redirect)
        client.commercial_owner = new_owner
        _assign_client_code(client, new_owner, force=True)
        client.save(update_fields=['commercial_owner', 'code', 'updated_at'])
        Project.objects.filter(client_id=client.id).update(commercial_agent=new_owner)
        messages.success(
            request,
            f'Client « {client.name} » affecté à {new_owner.get_display_name()}.',
        )
        return redirect(default_redirect)

    if action == 'merge_clients':
        keep = FinanceClient.objects.filter(id=request.POST.get('keep_id')).first()
        absorb = FinanceClient.objects.filter(id=request.POST.get('absorb_id')).first()
        if (
            not keep
            or not absorb
            or not can_edit_crm_client(request.user, keep)
            or not can_edit_crm_client(request.user, absorb)
        ):
            messages.error(request, 'Fusion impossible.')
            return redirect(default_redirect)
        ok, error = _merge_crm_clients(keep, absorb)
        if not ok:
            messages.error(request, error)
            return _crm_redirect(request, path=default_redirect, open=str(keep.id))
        messages.success(request, f'« {absorb.name} » fusionné dans « {keep.name} ».')
        return _crm_redirect(request, path=default_redirect, open=str(keep.id))

    payload = _client_form_payload(request)
    if not payload['name']:
        messages.error(request, 'Le nom / société est obligatoire.')
        return redirect(default_redirect)

    if action == 'update':
        client = FinanceClient.objects.filter(id=request.POST.get('client_id')).first()
        if not client or not can_edit_crm_client(request.user, client):
            messages.error(request, 'Client introuvable ou non autorisé.')
            return redirect(default_redirect)
        duplicate = _find_duplicate_client(
            name=payload['name'], phone=payload['phone'], exclude_id=client.id
        )
        if duplicate:
            messages.error(request, f'Un autre client existe déjà : « {duplicate.name} ».')
            return _crm_redirect(request, path=default_redirect, open=str(duplicate.id))
        for key, value in payload.items():
            setattr(client, key, value)
        old_owner_id = client.commercial_owner_id
        client.commercial_owner = _resolve_commercial_owner(
            request, default_owner=client.commercial_owner or request.user
        )
        if not client.code or client.commercial_owner_id != old_owner_id:
            _assign_client_code(
                client, client.commercial_owner, force=bool(client.commercial_owner_id != old_owner_id)
            )
        client.save()
        messages.success(request, f'Fiche client mise à jour ({client.code}).')
        return _crm_redirect(request, path=reverse('crm_my_clients'), open=str(client.id))

    duplicate = _find_duplicate_client(name=payload['name'], phone=payload['phone'])
    if duplicate:
        messages.warning(request, f'Le client « {duplicate.name} » existe déjà.')
        return _crm_redirect(request, path=reverse('crm_my_clients'), open=str(duplicate.id))

    owner = _resolve_commercial_owner(request, default_owner=request.user)
    client = FinanceClient(
        created_by=request.user,
        commercial_owner=owner,
        **payload,
    )
    _assign_client_code(client, owner, force=True)
    client.save()
    messages.success(request, f'Client « {client.name} » ajouté ({client.code}).')
    return _crm_redirect(request, path=reverse('crm_my_clients'), open=str(client.id))


def _portfolio_list_context(request, ctx):
    user = request.user
    see_all = ctx['view_all']
    filter_owner_id = ctx['filter_owner_id']
    search_q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    reste_filter = request.GET.get('reste', '').strip() == '1'
    show_archived = request.GET.get('archived') == '1'

    if status_filter and status_filter not in {key for key, _ in CLIENT_STATUS_CHOICES}:
        status_filter = ''

    clients_qs = _crm_clients_queryset(
        user,
        show_archived=show_archived,
        owner_filter=filter_owner_id,
        see_all=see_all,
    ).prefetch_related(Prefetch('follow_ups', queryset=ctx['follow_ups_qs']))

    if search_q:
        clients_qs = clients_qs.filter(
            Q(name__icontains=search_q)
            | Q(code__icontains=search_q)
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

    visible_active = _crm_clients_queryset(
        user, show_archived=False, owner_filter=filter_owner_id, see_all=see_all
    )
    portfolio_count = visible_active.count()
    if filter_owner_id:
        my_portfolio_count = FinanceClient.objects.filter(
            is_active=True, commercial_owner_id=filter_owner_id
        ).count()
    else:
        my_portfolio_count = FinanceClient.objects.filter(
            is_active=True, commercial_owner=user
        ).count()

    portfolio_total = sum((row['total_contract'] for row in clients_with_finance), Decimal('0.00'))
    portfolio_paid = sum((row['paid'] for row in clients_with_finance), Decimal('0.00'))

    return {
        'clients_with_finance': clients_with_finance,
        'show_archived': show_archived,
        'search_q': search_q,
        'status_filter': status_filter,
        'reste_filter': reste_filter,
        'portfolio_count': portfolio_count,
        'my_portfolio_count': my_portfolio_count,
        'portfolio_total': portfolio_total,
        'portfolio_paid': portfolio_paid,
        'portfolio_remaining': portfolio_total - portfolio_paid,
    }


def _render_crm(request, template, page_key, extra=None):
    blocked = _crm_guard(request)
    if blocked:
        return blocked
    ctx = _crm_shared_context(request, page_key=page_key)
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)


@login_required(login_url='login')
def crm_dashboard(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked

    ctx = _crm_shared_context(request, page_key='dashboard')
    overdue, due_today, upcoming, _without_date = _crm_prospect_relance(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    recouvrement_rows, total_remaining = _crm_recouvrement_rows(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    clients = list(
        _crm_clients_queryset(
            request.user,
            show_archived=False,
            owner_filter=ctx['filter_owner_id'],
            see_all=ctx['view_all'],
        )
    )
    clients_with_finance = _build_clients_with_finance(clients)
    reports_qs = _crm_reports_for_charts(request.user, see_all=ctx['view_all'])
    ctx.update({
        'prospect_overdue_count': len(overdue),
        'prospect_today_count': len(due_today),
        'recouvrement_count': len(recouvrement_rows),
        'total_remaining': total_remaining,
        'page_title': 'Dashboard',
        'page_intro': (
            'Vue synthèse CRM : graphiques consolidés sur les prospects, '
            'clients, encaissements et rapports commerciaux.'
        ),
        'mw_charts': crm_dashboard_all_charts(
            request.user,
            see_all=ctx['view_all'],
            owner_filter=ctx['filter_owner_id'],
            prospect_overdue=len(overdue),
            prospect_today=len(due_today),
            prospect_upcoming=len(upcoming),
            recouvrement_rows=recouvrement_rows,
            clients_with_finance=clients_with_finance,
            reports_qs=reports_qs,
            show_leaderboard=ctx['view_all'],
        ),
    })
    return render(request, 'crm/dashboard.html', ctx)


@login_required(login_url='login')
def crm_vente(request, period):
    blocked = _crm_guard(request)
    if blocked:
        return blocked

    if period not in CRM_VENTE_PERIODS:
        return redirect('crm_vente_day')

    ctx = _crm_shared_context(request, page_key=f'vente_{period}')
    selected_raw = request.GET.get('date', '').strip()
    try:
        selected_date = datetime.strptime(selected_raw, '%Y-%m-%d').date() if selected_raw else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    start, end, period_label = _crm_vente_bounds(period, selected_date)
    incomes_qs = _crm_income_queryset(
        request.user,
        see_all=ctx['view_all'],
        owner_filter=ctx['filter_owner_id'],
    ).filter(income_date__gte=start, income_date__lte=end)
    incomes = list(incomes_qs.order_by('-income_date', '-created_at'))
    total_amount = incomes_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    ctx.update({
        'vente_period': period,
        'vente_period_label': CRM_VENTE_PERIODS[period],
        'period_range_label': period_label,
        'selected_date': selected_date,
        'vente_incomes': incomes,
        'vente_total': total_amount,
        'vente_count': len(incomes),
        'page_title': f'Vente — {CRM_VENTE_PERIODS[period]}',
        'page_intro': (
            'Encaissements enregistrés par le service Finance, '
            'filtrés sur votre portefeuille commercial.'
        ),
        'mw_charts': [],
    })
    return render(request, 'crm/vente.html', ctx)


@login_required(login_url='login')
def crm_my_clients(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked
    default = reverse('crm_my_clients')
    post_response = _handle_crm_post(request, default_redirect=default)
    if post_response:
        return post_response

    ctx = _crm_shared_context(request, page_key='my_clients')
    portfolio_ctx = _portfolio_list_context(request, ctx)
    ctx.update(portfolio_ctx)
    open_client_id = request.GET.get('open', '').strip() or request.GET.get('edit', '').strip()
    if open_client_id and not any(
        str(row['client'].id) == open_client_id for row in portfolio_ctx['clients_with_finance']
    ):
        open_client_id = ''
    ctx.update({
        'open_client_id': open_client_id,
        'page_title': 'Mes clients',
        'page_intro': (
            'Liste compacte de votre portefeuille. Cliquez sur une ligne '
            'pour afficher la fiche complète du client.'
        ),
        'mw_charts': [],
    })
    return render(request, 'crm/my_clients.html', ctx)


@login_required(login_url='login')
def crm_relance(request):
    """Vue d'ensemble relances — distincte de Prospect et Recouvrement."""
    blocked = _crm_guard(request)
    if blocked:
        return blocked

    ctx = _crm_shared_context(request, page_key='relance')
    overdue, due_today, upcoming, without_date = _crm_prospect_relance(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    recouvrement_rows, total_remaining = _crm_recouvrement_rows(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    ctx.update({
        'prospect_overdue_count': len(overdue),
        'prospect_today_count': len(due_today),
        'prospect_upcoming_count': len(upcoming),
        'recouvrement_count': len(recouvrement_rows),
        'total_remaining': total_remaining,
        'page_title': 'Relance',
        'page_intro': (
            'Centre de relance commerciale : consultez vos priorités prospect '
            'et recouvrement, puis accédez au détail de chaque vue.'
        ),
        'mw_charts': [],
    })
    return render(request, 'crm/relance.html', ctx)


@login_required(login_url='login')
def crm_relance_prospect(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked
    default = reverse('crm_relance_prospect')
    post_response = _handle_crm_post(request, default_redirect=default)
    if post_response:
        return post_response

    ctx = _crm_shared_context(request, page_key='relance_prospect')
    overdue, due_today, upcoming, without_date = _crm_prospect_relance(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    ctx.update({
        'overdue_clients': overdue,
        'due_today_clients': due_today,
        'upcoming_clients': upcoming,
        'without_date_clients': without_date,
        'page_title': 'Relance — Prospect',
        'page_intro': (
            'Suivi des prospects à contacter : relances en retard, du jour et à venir. '
            'Mettez à jour la prochaine action depuis la fiche client.'
        ),
        'mw_charts': [],
    })
    return render(request, 'crm/relance_prospect.html', ctx)


@login_required(login_url='login')
def crm_relance_recouvrement(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked

    ctx = _crm_shared_context(request, page_key='relance_recouvrement')
    rows, total_remaining = _crm_recouvrement_rows(
        request.user,
        owner_filter=ctx['filter_owner_id'],
        see_all=ctx['view_all'],
    )
    ctx.update({
        'recouvrement_rows': rows,
        'total_remaining': total_remaining,
        'page_title': 'Relance — Recouvrement',
        'page_intro': (
            'Clients avec un reste à encaisser sur leurs projets. '
            'Les paiements sont enregistrés par le service Finance ; '
            'utilisez cette vue pour prioriser vos relances de recouvrement.'
        ),
        'mw_charts': [],
    })
    return render(request, 'crm/relance_recouvrement.html', ctx)


@login_required(login_url='login')
def crm_new_client(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked
    default = reverse('crm_new_client')
    post_response = _handle_crm_post(request, default_redirect=default)
    if post_response:
        return post_response

    ctx = _crm_shared_context(request, page_key='new_client')
    ctx.update({
        'edit_client': None,
        'page_title': 'Nouveau client',
        'page_intro': (
            'Créez une fiche client dans votre portefeuille. '
            'Le code (ex. CLI-CK-0001) est généré automatiquement.'
        ),
    })
    return render(request, 'crm/new_client.html', ctx)


@login_required(login_url='login')
def crm_reassign(request):
    blocked = _crm_guard(request)
    if blocked:
        return blocked
    if not can_reassign_crm_client(request.user):
        messages.error(request, 'Affectation réservée à la responsabilité commerciale et à la direction.')
        return redirect('crm_my_clients')

    default = reverse('crm_reassign')
    post_response = _handle_crm_post(request, default_redirect=default)
    if post_response:
        return post_response

    ctx = _crm_shared_context(request, page_key='reassign')
    ctx.update({
        'page_title': 'Affecter un client',
        'page_intro': (
            'Réassignez un client à un commercial responsable. '
            'Les projets liés héritent du nouveau commercial.'
        ),
    })
    return render(request, 'crm/reassign.html', ctx)
