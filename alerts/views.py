from collections import OrderedDict

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import alert_counts, collect_team_alerts

# Ordre d’affichage des catégories
CATEGORY_ORDER = (
    'Projets',
    'Stock',
    'Achats',
    'Machines',
    'CRM',
)


def _group_by_category(alerts):
    groups = OrderedDict()
    for name in CATEGORY_ORDER:
        groups[name] = []
    for alert in alerts:
        key = alert.get('module') or 'Autres'
        if key not in groups:
            groups[key] = []
        groups[key].append(alert)
    # Retirer les catégories vides pour l’affichage groupé
    return OrderedDict((k, v) for k, v in groups.items() if v)


@login_required(login_url='login')
def alerts_center(request):
    level = request.GET.get('level', '').strip()
    module = request.GET.get('module', '').strip()

    alerts = collect_team_alerts()
    counts = alert_counts(alerts)

    # Compteurs par catégorie (avant filtre niveau/module)
    category_tabs = []
    for name in CATEGORY_ORDER:
        n = sum(1 for a in alerts if a.get('module') == name)
        if n:
            category_tabs.append({'value': name, 'label': name, 'count': n})
    for alert in alerts:
        name = alert.get('module') or 'Autres'
        if name not in CATEGORY_ORDER and not any(t['value'] == name for t in category_tabs):
            category_tabs.append({
                'value': name,
                'label': name,
                'count': sum(1 for a in alerts if a.get('module') == name),
            })

    modules = [t['value'] for t in category_tabs]

    if level in {'red', 'orange', 'green'}:
        alerts = [a for a in alerts if a['level'] == level]
    if module:
        alerts = [a for a in alerts if a['module'] == module]

    alert_groups = _group_by_category(alerts)

    from reports.chart_data import build_alerts_charts

    return render(
        request,
        'alerts/center.html',
        {
            'alerts': alerts,
            'alert_groups': alert_groups,
            'counts': counts,
            'category_tabs': category_tabs,
            'modules': modules,
            'selected_level': level,
            'selected_module': module,
            'mw_charts': build_alerts_charts(counts, category_tabs),
        },
    )
