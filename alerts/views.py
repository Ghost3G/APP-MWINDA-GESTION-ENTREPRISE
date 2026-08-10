from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import alert_counts, collect_team_alerts


@login_required(login_url='login')
def alerts_center(request):
    level = request.GET.get('level', '').strip()
    module = request.GET.get('module', '').strip()

    alerts = collect_team_alerts()
    counts = alert_counts(alerts)

    modules = sorted({a['module'] for a in alerts})
    if level in {'red', 'orange', 'green'}:
        alerts = [a for a in alerts if a['level'] == level]
    if module:
        alerts = [a for a in alerts if a['module'] == module]

    return render(
        request,
        'alerts/center.html',
        {
            'alerts': alerts,
            'counts': counts,
            'modules': modules,
            'selected_level': level,
            'selected_module': module,
        },
    )
