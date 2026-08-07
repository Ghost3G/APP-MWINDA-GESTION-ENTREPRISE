from django.db import migrations


def _initials(owner):
    if not owner:
        return 'XX'
    first = (owner.first_name or '').strip()
    last = (owner.last_name or '').strip()
    if first and last:
        return (first[0] + last[0]).upper()
    parts = [p for p in (owner.username or '').replace('_', '.').split('.') if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts and len(parts[0]) >= 2:
        return parts[0][:2].upper()
    if first:
        return (first[:2]).upper()
    return 'XX'


def backfill_codes(apps, schema_editor):
    import re

    FinanceClient = apps.get_model('reports', 'FinanceClient')
    User = apps.get_model('users', 'User')

    clients = list(
        FinanceClient.objects.filter(code__isnull=True).select_related('commercial_owner').order_by('id')
    )
    clients += list(
        FinanceClient.objects.filter(code='').select_related('commercial_owner').order_by('id')
    )
    # Deduplicate by id
    seen = set()
    ordered = []
    for c in clients:
        if c.id in seen:
            continue
        seen.add(c.id)
        ordered.append(c)

    for client in ordered:
        owner = client.commercial_owner
        initials = _initials(owner)
        prefix = f'CLI-{initials}'
        pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$', re.IGNORECASE)
        max_n = 0
        for code in FinanceClient.objects.filter(code__istartswith=f'{prefix}-').values_list('code', flat=True):
            match = pattern.match(code or '')
            if match:
                max_n = max(max_n, int(match.group(1)))
        client.code = f'{prefix}-{max_n + 1:04d}'
        client.save(update_fields=['code'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0011_client_code'),
    ]

    operations = [
        migrations.RunPython(backfill_codes, noop_reverse),
    ]
