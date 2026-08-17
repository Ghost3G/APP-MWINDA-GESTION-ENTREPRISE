"""Agrégation des alertes métier pour le Centre des alertes (visible par tous)."""

from datetime import timedelta

from django.db import OperationalError, ProgrammingError
from django.db.models import F
from django.urls import reverse
from django.utils import timezone


def _item(*, level, icon, module, title, detail='', url='', sort_date=None):
    level_rank = {'red': 0, 'orange': 1, 'green': 2}.get(level, 9)
    return {
        'level': level,
        'icon': icon,
        'module': module,
        'title': title,
        'detail': detail,
        'url': url,
        'sort_date': sort_date or timezone.localdate(),
        'level_rank': level_rank,
    }


def collect_team_alerts(*, limit=120):
    """
    Collecte les alertes transverses pour motiver / aligner l'équipe.
    Tout le monde voit le même centre (vue équipe).
    """
    today = timezone.localdate()
    project_soon = today + timedelta(days=2)
    recent = today - timedelta(days=7)
    alerts = []

    # --- Projets ---
    try:
        from projects.models import Project

        for project in (
            Project.objects.exclude(status='done')
            .filter(end_date__lt=today)
            .order_by('end_date', 'name')[:40]
        ):
            days = (today - project.end_date).days
            alerts.append(
                _item(
                    level='red',
                    icon='🔴',
                    module='Projets',
                    title=f'Projet « {project.name} » en retard',
                    detail=f'Échéance {project.end_date.strftime("%d/%m/%Y")} ({days} j de retard)',
                    url=reverse('project_detail', args=[project.id]),
                    sort_date=project.end_date,
                )
            )

        for project in (
            Project.objects.exclude(status='done')
            .filter(end_date__gte=today, end_date__lte=project_soon)
            .order_by('end_date', 'name')[:30]
        ):
            days = (project.end_date - today).days
            when = "aujourd’hui" if days == 0 else f'dans {days} j'
            alerts.append(
                _item(
                    level='orange',
                    icon='🟠',
                    module='Projets',
                    title=f'Projet « {project.name} » — échéance proche',
                    detail=f'Échéance {project.end_date.strftime("%d/%m/%Y")} ({when})',
                    url=reverse('project_detail', args=[project.id]),
                    sort_date=project.end_date,
                )
            )

        for project in Project.objects.filter(status='awaiting_delivery').order_by(
            'end_date', 'name'
        )[:20]:
            alerts.append(
                _item(
                    level='orange',
                    icon='🟠',
                    module='Projets',
                    title=f'Projet « {project.name} » en attente de livraison',
                    detail='À finaliser côté logistique / livraison',
                    url=reverse('project_detail', args=[project.id]),
                    sort_date=project.end_date or today,
                )
            )

        for project in Project.objects.filter(status='done', end_date__gte=recent).order_by(
            '-end_date', 'name'
        )[:15]:
            alerts.append(
                _item(
                    level='green',
                    icon='🟢',
                    module='Projets',
                    title=f'Livraison / projet « {project.name} » terminé',
                    detail=f'Clôturé — échéance {project.end_date.strftime("%d/%m/%Y")}',
                    url=reverse('project_detail', args=[project.id]),
                    sort_date=project.end_date,
                )
            )
    except (OperationalError, ProgrammingError):
        pass

    # --- Stock & Achats ---
    try:
        from inventory.models import PurchaseRequest, StockItem

        for item in (
            StockItem.objects.filter(is_active=True)
            .filter(quantity__lte=F('min_stock'))
            .order_by('quantity', 'name')[:40]
        ):
            qty = item.quantity
            level = 'red' if qty <= 0 else 'orange'
            icon = '🔴' if level == 'red' else '🟠'
            title = (
                f'Stock « {item.name} » épuisé'
                if qty <= 0
                else f'Stock « {item.name} » presque épuisé'
            )
            alerts.append(
                _item(
                    level=level,
                    icon=icon,
                    module='Stock',
                    title=title,
                    detail=(
                        f'{qty} {item.get_unit_display().lower()} '
                        f'(minimum {item.min_stock})'
                    ),
                    url=reverse('stock_dashboard') + '?critical=1',
                    sort_date=today,
                )
            )

        for purchase in (
            PurchaseRequest.objects.filter(status__in=['approved', 'ordered'])
            .select_related('item')
            .order_by('-updated_at', '-id')[:15]
        ):
            alerts.append(
                _item(
                    level='green',
                    icon='🟢',
                    module='Achats',
                    title=(
                        f'Commande / DA « {purchase.item.name} » — '
                        f'{purchase.get_status_display().lower()}'
                    ),
                    detail=(
                        f'Quantité {purchase.quantity} '
                        f'{purchase.item.get_unit_display().lower()}'
                    ),
                    url=reverse('stock_dashboard'),
                    sort_date=purchase.updated_at.date() if purchase.updated_at else today,
                )
            )
    except (OperationalError, ProgrammingError):
        pass

    # --- Machines ---
    try:
        from machines.models import Machine

        for machine in Machine.objects.filter(is_active=True):
            detail_url = reverse('machine_detail', args=[machine.id])
            if machine.is_broken:
                alerts.append(
                    _item(
                        level='red',
                        icon='🔴',
                        module='Machines',
                        title=f'Machine « {machine.name} » en panne',
                        detail='Intervention technique requise',
                        url=detail_url,
                        sort_date=today,
                    )
                )
            elif machine.maintenance_overdue:
                alerts.append(
                    _item(
                        level='red',
                        icon='🔴',
                        module='Machines',
                        title=f'Machine « {machine.name} » — maintenance en retard',
                        detail=(
                            f'Prévue le {machine.next_maintenance.strftime("%d/%m/%Y")}'
                            if machine.next_maintenance
                            else ''
                        ),
                        url=detail_url,
                        sort_date=machine.next_maintenance or today,
                    )
                )
            elif machine.maintenance_soon:
                days = machine.days_until_maintenance
                alerts.append(
                    _item(
                        level='orange',
                        icon='🟠',
                        module='Machines',
                        title=f'Machine « {machine.name} » — maintenance dans {days} j',
                        detail=(
                            f'Prévue le {machine.next_maintenance.strftime("%d/%m/%Y")}'
                            if machine.next_maintenance
                            else ''
                        ),
                        url=detail_url,
                        sort_date=machine.next_maintenance or today,
                    )
                )
            if machine.has_part_to_replace:
                alerts.append(
                    _item(
                        level='orange',
                        icon='🟠',
                        module='Machines',
                        title=(
                            f'Machine « {machine.name} » — '
                            'pièce / consommable à remplacer'
                        ),
                        detail='Vérifier les consommables sur la fiche',
                        url=detail_url,
                        sort_date=today,
                    )
                )
    except (OperationalError, ProgrammingError):
        pass

    # --- CRM ---
    try:
        from reports.models import FinanceClient

        for client in (
            FinanceClient.objects.filter(is_active=True)
            .exclude(next_action_date__isnull=True)
            .filter(next_action_date__lt=today)
            .exclude(status__in=['inactive', 'lost'])
            .order_by('next_action_date', 'name')[:30]
        ):
            alerts.append(
                _item(
                    level='orange',
                    icon='🟠',
                    module='CRM',
                    title=f'Client « {client.name} » à relancer',
                    detail=(
                        f'Action prévue le {client.next_action_date.strftime("%d/%m/%Y")}'
                        + (f' — {client.next_action}' if client.next_action else '')
                    ),
                    url=reverse('crm_my_clients') + f'?edit={client.id}',
                    sort_date=client.next_action_date,
                )
            )

        for client in (
            FinanceClient.objects.filter(is_active=True, next_action_date=today)
            .exclude(status__in=['inactive', 'lost'])
            .order_by('name')[:20]
        ):
            alerts.append(
                _item(
                    level='orange',
                    icon='🟠',
                    module='CRM',
                    title=f'Client « {client.name} » — relance aujourd’hui',
                    detail=client.next_action or 'Prochaine action commerciale',
                    url=reverse('crm_my_clients') + f'?edit={client.id}',
                    sort_date=today,
                )
            )

        from django.contrib.auth import get_user_model
        from reports.models import CrmCommercialReport

        User = get_user_model()
        week_ago = today - timedelta(days=7)
        commercial_ids_with_report = set(
            CrmCommercialReport.objects.filter(activity_date__gte=week_ago)
            .values_list('author_id', flat=True)
            .distinct()
        )
        for agent in User.objects.filter(is_active=True, org_group='commercial').order_by('first_name', 'last_name')[:30]:
            if agent.id not in commercial_ids_with_report:
                alerts.append(
                    _item(
                        level='orange',
                        icon='🟠',
                        module='CRM',
                        title=f'Commercial {agent.get_display_name()} — aucun rapport depuis 7 jours',
                        detail='Encourager un compte rendu d’activité client dans Rapports CRM',
                        url=reverse('crm_reports_list'),
                        sort_date=week_ago,
                    )
                )

        for report in (
            CrmCommercialReport.objects.filter(status='submitted')
            .select_related('client', 'author')
            .filter(result__in=['quote_requested', 'payment_promised'])
            .order_by('-activity_date')[:15]
        ):
            client_name = report.client.name if report.client_id else 'Client'
            author_name = report.author.get_display_name() if report.author_id else 'Commercial'
            alerts.append(
                _item(
                    level='orange',
                    icon='🟠',
                    module='CRM',
                    title=f'Rapport CRM — {report.get_result_display()} ({client_name})',
                    detail=f'{author_name} · {report.activity_date.strftime("%d/%m/%Y")}',
                    url=reverse('crm_report_detail', args=[report.id]),
                    sort_date=report.activity_date,
                )
            )
    except (OperationalError, ProgrammingError):
        pass

    alerts.sort(key=lambda a: (a['level_rank'], a['sort_date'], a['title']))
    return alerts[:limit]


def count_actionable_alerts():
    """Compteur léger (🔴 + 🟠) pour le badge du menu."""
    today = timezone.localdate()
    project_soon = today + timedelta(days=2)
    total = 0

    try:
        from projects.models import Project

        total += (
            Project.objects.exclude(status='done')
            .filter(end_date__lte=project_soon)
            .count()
        )
        total += Project.objects.filter(status='awaiting_delivery').count()
    except (OperationalError, ProgrammingError):
        pass

    try:
        from inventory.models import StockItem

        total += (
            StockItem.objects.filter(is_active=True)
            .filter(quantity__lte=F('min_stock'))
            .count()
        )
    except (OperationalError, ProgrammingError):
        pass

    try:
        from machines.models import Machine

        soon = today + timedelta(days=7)
        total += Machine.objects.filter(is_active=True, status='broken').count()
        total += (
            Machine.objects.filter(is_active=True)
            .exclude(next_maintenance__isnull=True)
            .filter(next_maintenance__lte=soon)
            .count()
        )
    except (OperationalError, ProgrammingError):
        pass

    try:
        from reports.models import FinanceClient

        total += (
            FinanceClient.objects.filter(is_active=True)
            .exclude(next_action_date__isnull=True)
            .filter(next_action_date__lte=today)
            .exclude(status__in=['inactive', 'lost'])
            .count()
        )
    except (OperationalError, ProgrammingError):
        pass

    return total


def alert_counts(alerts=None):
    if alerts is None:
        alerts = collect_team_alerts()
    return {
        'total': len(alerts),
        'red': sum(1 for a in alerts if a['level'] == 'red'),
        'orange': sum(1 for a in alerts if a['level'] == 'orange'),
        'green': sum(1 for a in alerts if a['level'] == 'green'),
        'actionable': sum(1 for a in alerts if a['level'] in {'red', 'orange'}),
    }
