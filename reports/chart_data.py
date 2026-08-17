"""Agrégations pour graphiques MWINDA (Chart.js)."""
from calendar import monthrange
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from projects.models import Project

from .models import CrmCommercialReport, CrmFollowUp, FinanceClient, FinanceIncome

MW_PALETTE = [
    '#fde047',
    '#4ade80',
    '#60a5fa',
    '#fb923c',
    '#a78bfa',
    '#f87171',
    '#2dd4bf',
    '#f472b6',
]

STATUS_COLORS = {
    'prospect': '#fde047',
    'active': '#4ade80',
    'inactive': '#71717a',
    'lost': '#f87171',
}


def _chart(chart_id, chart_type, title, *, labels, values, colors=None, subtitle='', wide=False, height=260, value_suffix=''):
    vals = [float(v) for v in values]
    if not any(vals):
        return None
    return {
        'id': chart_id,
        'type': chart_type,
        'title': title,
        'subtitle': subtitle,
        'labels': list(labels),
        'values': vals,
        'colors': list(colors or MW_PALETTE[: len(labels)]),
        'wide': wide,
        'height': height,
        'value_suffix': value_suffix,
    }


def _doughnut(chart_id, title, labels, values, colors=None, **kwargs):
    return _chart(chart_id, 'doughnut', title, labels=labels, values=values, colors=colors, **kwargs)


def _bar(chart_id, title, labels, values, colors=None, **kwargs):
    return _chart(chart_id, 'bar', title, labels=labels, values=values, colors=colors, **kwargs)


def _bar_horizontal(chart_id, title, labels, values, colors=None, **kwargs):
    return _chart(chart_id, 'bar_horizontal', title, labels=labels, values=values, colors=colors, **kwargs)


def _line(chart_id, title, labels, values, *, dataset_label='Valeur', colors=None, **kwargs):
    chart = _chart(chart_id, 'line', title, labels=labels, values=values, colors=colors, **kwargs)
    if chart:
        chart['dataset_label'] = dataset_label
        if '$' in title or 'Montant' in dataset_label:
            chart['value_suffix'] = '$'
    return chart


def build_crm_status_donut(clients_qs):
    status_labels = dict(FinanceClient._meta.get_field('status').choices)
    counts = Counter(clients_qs.values_list('status', flat=True))
    labels = []
    values = []
    colors = []
    for key, label in status_labels.items():
        count = counts.get(key, 0)
        if count:
            labels.append(label)
            values.append(count)
            colors.append(STATUS_COLORS.get(key, MW_PALETTE[len(colors) % len(MW_PALETTE)]))
    return _doughnut(
        'crm-chart-status',
        'Répartition par statut',
        labels,
        values,
        colors=colors,
        subtitle='Fiches clients actives',
    )


def build_crm_top_remaining(clients_with_finance, *, limit=8):
    rows = sorted(
        [r for r in clients_with_finance if r['remaining'] > 0],
        key=lambda r: (-r['remaining'], r['client'].name.lower()),
    )[:limit]
    if not rows:
        return None
    labels = [r['client'].name[:22] for r in rows]
    values = [float(r['remaining']) for r in rows]
    colors = ['#f87171'] * len(rows)
    return _bar_horizontal(
        'crm-chart-top-reste',
        'Top clients — reste à encaisser ($)',
        labels,
        values,
        colors=colors,
        subtitle='Priorité recouvrement',
        value_suffix='$',
    )


def build_crm_relance_split(prospect_count, recouvrement_count):
    if prospect_count <= 0 and recouvrement_count <= 0:
        return None
    return _doughnut(
        'crm-chart-relance-split',
        'Focus relances',
        ['Prospects à suivre', 'Recouvrement ($)'],
        [prospect_count, recouvrement_count],
        colors=['#fde047', '#f87171'],
        subtitle='Volume prospect vs dossiers avec reste',
    )


def build_crm_prospect_status(prospect_qs):
    status_labels = dict(FinanceClient._meta.get_field('status').choices)
    counts = Counter(prospect_qs.values_list('status', flat=True))
    labels = []
    values = []
    colors = []
    for key in ('prospect', 'active', 'inactive', 'lost'):
        count = counts.get(key, 0)
        if count:
            labels.append(status_labels.get(key, key))
            values.append(count)
            colors.append(STATUS_COLORS.get(key, '#fde047'))
    return _doughnut(
        'crm-chart-prospect-status',
        'Prospects par statut',
        labels,
        values,
        colors=colors,
    )


def build_crm_followups_line(user, *, see_all, weeks=6):
    today = timezone.localdate()
    start = today - timedelta(days=(weeks - 1) * 7)
    qs = CrmFollowUp.objects.filter(created_at__date__gte=start)
    if not see_all:
        qs = qs.filter(client__commercial_owner=user)
    buckets = defaultdict(int)
    for row in qs.values_list('created_at', flat=True):
        d = timezone.localtime(row).date()
        week_start = d - timedelta(days=d.weekday())
        buckets[week_start] += 1
    if not buckets or not any(buckets.values()):
        return None
    ordered_weeks = sorted(buckets.keys())
    labels = [week.strftime('%d/%m') for week in ordered_weeks]
    values = [buckets[week] for week in ordered_weeks]
    return _line(
        'crm-chart-followups',
        'Activité commerciale (suivis)',
        labels,
        values,
        dataset_label='Suivis enregistrés',
        subtitle=f'{weeks} dernières semaines',
    )


def build_crm_monthly_income_line(user, *, see_all, months=6):
    today = timezone.localdate()
    start = today.replace(day=1)
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    qs = FinanceIncome.objects.filter(income_date__gte=start)
    if not see_all:
        qs = qs.filter(client__commercial_owner=user)
    rows = (
        qs.annotate(month=TruncMonth('income_date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    bucket = {row['month'].strftime('%b %Y'): float(row['total'] or 0) for row in rows if row['month']}
    if not bucket:
        return None
    labels = list(bucket.keys())
    values = list(bucket.values())
    return _line(
        'crm-chart-income-trend',
        'Encaissements reçus',
        labels,
        values,
        dataset_label='Montant ($)',
        subtitle='Données saisies par Finance',
        colors=['#4ade80'],
    )


def build_crm_reports_by_type(reports_qs):
    type_labels = dict(CrmCommercialReport.ACTIVITY_TYPE_CHOICES)
    counts = Counter(reports_qs.values_list('activity_type', flat=True))
    labels = []
    values = []
    for key, label in type_labels.items():
        count = counts.get(key, 0)
        if count:
            labels.append(label[:24])
            values.append(count)
    return _bar(
        'crm-chart-report-types',
        'Rapports par type d’activité',
        labels,
        values,
        subtitle='Période affichée',
        wide=True,
    )


def build_crm_reports_by_author(reports_qs):
    counts = Counter()
    for rep in reports_qs.select_related('author')[:500]:
        name = rep.author.get_display_name() if rep.author_id else '—'
        counts[name] += 1
    if not counts:
        return None
    top = counts.most_common(8)
    labels = [x[0][:18] for x in top]
    values = [x[1] for x in top]
    return _bar_horizontal(
        'crm-chart-report-authors',
        'Classement commerciaux',
        labels,
        values,
        colors=['#fde047'] * len(labels),
        subtitle='Nombre de rapports publiés',
    )


def build_crm_new_clients_line(user, *, see_all, months=6):
    today = timezone.localdate()
    start = today.replace(day=1)
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    qs = FinanceClient.objects.filter(is_active=True, created_at__date__gte=start)
    if not see_all:
        qs = qs.filter(commercial_owner=user)
    rows = (
        qs.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )
    bucket = {row['month'].strftime('%b %Y'): row['total'] for row in rows if row['month']}
    if not bucket or not any(bucket.values()):
        return None
    labels = list(bucket.keys())
    values = list(bucket.values())
    return _bar(
        'crm-chart-new-clients',
        'Nouvelles fiches clients',
        labels,
        values,
        colors=['#60a5fa'] * len(labels),
        subtitle='Créations par mois',
    )


def build_crm_prospect_pipeline(prospect_overdue, prospect_today, prospect_upcoming):
    total = prospect_overdue + prospect_today + prospect_upcoming
    if total <= 0:
        return None
    return _bar(
        'crm-chart-prospect-pipeline',
        'Pipeline prospects',
        ['En retard', 'Aujourd\'hui', 'À venir'],
        [prospect_overdue, prospect_today, prospect_upcoming],
        colors=['#f87171', '#fde047', '#4ade80'],
        subtitle='Actions planifiées',
    )


def build_projects_status_chart(projects_qs):
    status_labels = dict(Project.STATUS_CHOICES)
    counts = Counter(projects_qs.values_list('status', flat=True))
    labels = []
    values = []
    colors = []
    color_map = {
        'pending': '#fde047',
        'progress': '#60a5fa',
        'awaiting_delivery': '#fb923c',
        'done': '#4ade80',
        'urgent': '#f87171',
    }
    for key, label in status_labels.items():
        count = counts.get(key, 0)
        if count:
            labels.append(label)
            values.append(count)
            colors.append(color_map.get(key, MW_PALETTE[len(colors) % len(MW_PALETTE)]))
    return _doughnut(
        'projects-chart-status',
        'Projets par statut',
        labels,
        values,
        colors=colors,
        subtitle='Vue portefeuille projets',
    )


def build_projects_branch_chart(projects_qs):
    from projects.branches import TECH_BRANCH_CHOICES

    branch_labels = dict(TECH_BRANCH_CHOICES)
    counts = Counter(projects_qs.values_list('branch', flat=True))
    labels = []
    values = []
    for key, label in branch_labels.items():
        count = counts.get(key, 0)
        if count:
            labels.append(label[:20])
            values.append(count)
    return _bar(
        'projects-chart-branch',
        'Répartition par branche',
        labels,
        values,
        subtitle='Metal design · Bois · Autres',
        wide=True,
    )


def build_finance_category_donut(category_rows, chart_id, title, *, subtitle='', value_suffix='$'):
    labels = []
    values = []
    for row in category_rows:
        total = float(row.get('total') or 0)
        if total > 0:
            labels.append(str(row.get('label', ''))[:20])
            values.append(total)
    return _doughnut(chart_id, title, labels, values, subtitle=subtitle, value_suffix=value_suffix)


def build_finance_monthly_trend(selected_date, *, months=6):
    from .views import _finance_totals

    today = selected_date
    labels = []
    entrees = []
    sorties = []
    cursor = today.replace(day=1)
    for _ in range(months):
        last_day = monthrange(cursor.year, cursor.month)[1]
        start = cursor
        end = cursor.replace(day=last_day)
        totals = _finance_totals(start, end)
        labels.insert(0, cursor.strftime('%b %Y'))
        entrees.insert(0, float(totals['entrees']))
        sorties.insert(0, float(totals['sorties']))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    if not any(entrees) and not any(sorties):
        return None
    return {
        'id': 'finance-chart-monthly-trend',
        'type': 'bar_grouped',
        'title': 'Tendance mensuelle',
        'subtitle': 'Entrées vs sorties — 6 derniers mois',
        'labels': labels,
        'datasets': [
            {'label': 'Entrées', 'values': entrees, 'color': '#4ade80'},
            {'label': 'Sorties', 'values': sorties, 'color': '#f87171'},
        ],
        'wide': True,
        'height': 280,
        'value_suffix': '$',
    }


def build_overtime_monthly_chart(summary_rows):
    buckets = defaultdict(float)
    for row in summary_rows:
        for entry in row.get('entries', []):
            key = entry.work_date.strftime('%b %Y')
            buckets[key] += float(entry.days)
    if not buckets:
        return None
    labels = list(buckets.keys())
    values = list(buckets.values())
    return _bar(
        'overtime-chart-monthly',
        'Jours sup. enregistrés',
        labels,
        values,
        colors=['#fde047'] * len(labels),
        subtitle='Répartition mensuelle',
    )


def build_overtime_by_agent_chart(summary_rows, *, limit=10):
    rows = sorted(summary_rows, key=lambda r: -float(r['total_days']))[:limit]
    if not rows or not any(float(r['total_days']) for r in rows):
        return None
    labels = [r['user'].get_display_name()[:16] for r in rows]
    values = [float(r['total_days']) for r in rows]
    return _bar_horizontal(
        'overtime-chart-agents',
        'Jours sup. par collaborateur',
        labels,
        values,
        colors=['#fde047'] * len(labels),
        subtitle='Période sélectionnée',
    )


def pack_charts(*charts):
    """Retourne une liste sans entrées vides."""
    return [chart for chart in charts if chart]


def crm_hub_charts(user, *, see_all, owner_filter, prospect_overdue, prospect_today, prospect_upcoming, recouvrement_rows):
    from .views import _build_clients_with_finance, _crm_clients_queryset

    clients = list(
        _crm_clients_queryset(user, show_archived=False, owner_filter=owner_filter, see_all=see_all)
    )
    with_finance = _build_clients_with_finance(clients)
    prospect_total = prospect_overdue + prospect_today + prospect_upcoming
    return pack_charts(
        build_crm_relance_split(prospect_total, len(recouvrement_rows)),
        build_crm_top_remaining(with_finance, limit=6),
        build_crm_monthly_income_line(user, see_all=see_all),
    )


def crm_my_clients_charts(user, *, see_all, owner_filter, clients_with_finance):
    from .views import _crm_clients_queryset

    qs = _crm_clients_queryset(
        user, show_archived=False, owner_filter=owner_filter, see_all=see_all
    )
    return pack_charts(
        build_crm_status_donut(qs),
        build_crm_top_remaining(clients_with_finance, limit=8),
        build_crm_monthly_income_line(user, see_all=see_all),
        build_crm_new_clients_line(user, see_all=see_all),
    )


def crm_prospect_charts(user, *, see_all, owner_filter, overdue, due_today, upcoming):
    from .views import _crm_clients_queryset

    prospect_qs = _crm_clients_queryset(
        user, show_archived=False, owner_filter=owner_filter, see_all=see_all
    ).filter(status='prospect')
    return pack_charts(
        build_crm_prospect_pipeline(len(overdue), len(due_today), len(upcoming)),
        build_crm_prospect_status(prospect_qs),
        build_crm_followups_line(user, see_all=see_all),
    )


def crm_recouvrement_charts(user, *, see_all, clients_with_finance):
    return pack_charts(
        build_crm_top_remaining(clients_with_finance, limit=10),
        build_crm_monthly_income_line(user, see_all=see_all),
    )


def crm_reports_charts(reports_qs, *, show_leaderboard):
    charts = [
        build_crm_reports_by_type(reports_qs),
    ]
    if show_leaderboard:
        author_chart = build_crm_reports_by_author(reports_qs)
        if author_chart:
            charts.append(author_chart)
    return pack_charts(*charts)


PROJECT_STATUS_LABELS = {
    'pending': 'En attente',
    'progress': 'En cours',
    'urgent': 'Urgent',
    'awaiting_delivery': 'Attente livraison',
    'done': 'Terminé',
}

TASK_STATUS_LABELS = {
    'pending': 'À faire',
    'in_progress': 'En cours',
    'done': 'Terminées',
}


def build_management_dashboard_charts(project_status_counts, task_status_counts, department_stats, worker_stats):
    proj_labels = []
    proj_values = []
    proj_colors = []
    color_map = {
        'pending': '#fde047',
        'progress': '#60a5fa',
        'urgent': '#f87171',
        'awaiting_delivery': '#fb923c',
        'done': '#4ade80',
    }
    for key, label in PROJECT_STATUS_LABELS.items():
        count = project_status_counts.get(key, 0)
        if count:
            proj_labels.append(label)
            proj_values.append(count)
            proj_colors.append(color_map.get(key, MW_PALETTE[len(proj_colors) % len(MW_PALETTE)]))

    task_labels = []
    task_values = []
    task_colors = []
    task_color_map = {
        'pending': '#fde047',
        'in_progress': '#60a5fa',
        'done': '#4ade80',
    }
    for key, label in TASK_STATUS_LABELS.items():
        count = task_status_counts.get(key, 0)
        if count:
            task_labels.append(label)
            task_values.append(count)
            task_colors.append(task_color_map.get(key, '#fde047'))

    dept_rows = [row for row in department_stats if row.get('total', 0) > 0]
    dept_labels = [row['label'][:18] for row in dept_rows[:8]]
    dept_values = [row['total'] for row in dept_rows[:8]]

    worker_rows = sorted(worker_stats, key=lambda r: -r.get('total', 0))[:8]
    worker_labels = [row['user'].get_display_name()[:16] for row in worker_rows]
    worker_values = [row['total'] for row in worker_rows]

    return pack_charts(
        _doughnut(
            'dash-chart-projects',
            'Projets par statut',
            proj_labels,
            proj_values,
            colors=proj_colors,
            subtitle='Vue direction',
        ),
        _doughnut(
            'dash-chart-tasks',
            'Tâches par statut',
            task_labels,
            task_values,
            colors=task_colors,
            subtitle='Ensemble des chantiers',
        ),
        _bar(
            'dash-chart-branches',
            'Charge par branche',
            dept_labels,
            dept_values,
            colors=['#60a5fa'] * len(dept_labels),
            subtitle='Nombre de tâches actives',
            wide=True,
        ) if dept_labels else None,
        _bar_horizontal(
            'dash-chart-agents',
            'Charge par agent',
            worker_labels,
            worker_values,
            colors=['#fde047'] * len(worker_labels),
            subtitle='Tâches assignées',
        ) if worker_labels else None,
    )


def build_agent_dashboard_charts(*, open_count, done_count, overdue_count, due_soon_count):
    charts = []
    if open_count + done_count > 0:
        charts.append(_doughnut(
            'dash-agent-tasks',
            'Mes tâches',
            ['À traiter', 'Terminées'],
            [open_count, done_count],
            colors=['#60a5fa', '#4ade80'],
            subtitle='Mon portefeuille',
        ))
    on_track = max(open_count - overdue_count - due_soon_count, 0)
    if overdue_count + due_soon_count + on_track > 0:
        charts.append(_bar(
            'dash-agent-deadlines',
            'Échéances',
            ['En retard', '≤ 3 jours', 'Dans les temps'],
            [overdue_count, due_soon_count, on_track],
            colors=['#f87171', '#fde047', '#4ade80'],
            subtitle='Priorités du jour',
        ))
    return pack_charts(*charts)


def build_tasks_manage_charts(stats):
    status_total = stats.get('pending', 0) + stats.get('in_progress', 0) + stats.get('done', 0)
    deadline_total = stats.get('overdue', 0) + stats.get('due_soon', 0)
    return pack_charts(
        _doughnut(
            'tasks-chart-status',
            'Répartition des statuts',
            ['À faire', 'En cours', 'Terminées'],
            [stats.get('pending', 0), stats.get('in_progress', 0), stats.get('done', 0)],
            colors=['#fde047', '#60a5fa', '#4ade80'],
            subtitle='Filtres actifs inclus',
        ) if status_total else None,
        _bar(
            'tasks-chart-deadlines',
            'Suivi des échéances',
            ['En retard', '≤ 3 jours'],
            [stats.get('overdue', 0), stats.get('due_soon', 0)],
            colors=['#f87171', '#fde047'],
            subtitle='Tâches non terminées',
        ) if deadline_total else None,
    )


def build_task_board_charts(columns, *, project_name=''):
    pending = len(columns.get('pending', []))
    in_progress = len(columns.get('in_progress', []))
    done = len(columns.get('done', []))
    total = pending + in_progress + done
    if total <= 0:
        return []
    subtitle = project_name[:40] if project_name else 'Projet sélectionné'
    return pack_charts(
        _doughnut(
            'board-chart-columns',
            'Tableau Kanban',
            ['À faire', 'En cours', 'Terminées'],
            [pending, in_progress, done],
            colors=['#fde047', '#60a5fa', '#4ade80'],
            subtitle=subtitle,
        ),
    )


def build_stock_charts(all_items, *, purchase_status_rows=None):
    from inventory.models import ITEM_CATEGORY_CHOICES

    cat_counts = Counter(item.category for item in all_items)
    cat_labels = []
    cat_values = []
    for key, label in ITEM_CATEGORY_CHOICES:
        count = cat_counts.get(key, 0)
        if count:
            cat_labels.append(label[:20])
            cat_values.append(count)

    critical = sum(1 for item in all_items if getattr(item, 'is_critical', False))
    ok_count = max(len(all_items) - critical, 0)

    charts = [
        _doughnut(
            'stock-chart-category',
            'Articles par catégorie',
            cat_labels,
            cat_values,
            subtitle='Stock actif',
        ) if cat_labels else None,
        _doughnut(
            'stock-chart-critical',
            'Niveaux de stock',
            ['Critique', 'Conforme'],
            [critical, ok_count],
            colors=['#f87171', '#4ade80'],
            subtitle='Seuils minimum',
        ) if all_items else None,
    ]

    if purchase_status_rows:
        from inventory.models import PURCHASE_STATUS_CHOICES

        status_labels = dict(PURCHASE_STATUS_CHOICES)
        p_labels = []
        p_values = []
        p_colors = ['#fde047', '#60a5fa', '#fb923c', '#4ade80', '#71717a']
        for idx, row in enumerate(purchase_status_rows):
            count = row.get('count', 0)
            if count:
                p_labels.append(status_labels.get(row.get('status'), row.get('status', '—'))[:18])
                p_values.append(count)
        if p_labels:
            charts.append(_doughnut(
                'stock-chart-purchases',
                'Demandes d\'achat',
                p_labels,
                p_values,
                colors=p_colors[: len(p_labels)],
                subtitle='Hors annulées',
            ))

    return pack_charts(*charts)


def build_alerts_charts(counts, category_tabs):
    level_labels = []
    level_values = []
    level_colors = {'red': '#f87171', 'orange': '#fb923c', 'green': '#4ade80'}
    colors = []
    for key, label in (('red', 'Urgent'), ('orange', 'Attention'), ('green', 'Info')):
        value = counts.get(key, 0)
        if value:
            level_labels.append(label)
            level_values.append(value)
            colors.append(level_colors[key])

    module_labels = [tab['label'][:16] for tab in category_tabs[:8]]
    module_values = [tab['count'] for tab in category_tabs[:8]]

    return pack_charts(
        _doughnut(
            'alerts-chart-levels',
            'Alertes par niveau',
            level_labels,
            level_values,
            colors=colors,
            subtitle=f"{counts.get('total', 0)} alertes actives",
        ) if level_labels else None,
        _bar_horizontal(
            'alerts-chart-modules',
            'Alertes par module',
            module_labels,
            module_values,
            colors=['#fde047'] * len(module_labels),
            subtitle='Vue équipe',
            wide=True,
        ) if module_labels else None,
    )


def build_machines_charts(machines, *, maintenance_count, broken_count, part_count):
    from machines.models import MACHINE_STATUS_CHOICES

    status_labels = dict(MACHINE_STATUS_CHOICES)
    status_counts = Counter(m.status for m in machines)
    labels = []
    values = []
    colors = []
    color_map = {'ok': '#4ade80', 'broken': '#f87171', 'standby': '#71717a'}
    for key, label in MACHINE_STATUS_CHOICES:
        count = status_counts.get(key, 0)
        if count:
            labels.append(label)
            values.append(count)
            colors.append(color_map.get(key, MW_PALETTE[len(colors) % len(MW_PALETTE)]))

    alert_total = maintenance_count + broken_count + part_count
    return pack_charts(
        _doughnut(
            'machines-chart-status',
            'Parc par statut',
            labels,
            values,
            colors=colors,
            subtitle=f'{len(machines)} machine(s) active(s)',
        ) if labels else None,
        _bar(
            'machines-chart-alerts',
            'Types d\'alertes',
            ['Maintenance', 'En panne', 'Pièce à remplacer'],
            [maintenance_count, broken_count, part_count],
            colors=['#fde047', '#f87171', '#fb923c'],
            subtitle='Priorités techniques',
        ) if alert_total else None,
    )
