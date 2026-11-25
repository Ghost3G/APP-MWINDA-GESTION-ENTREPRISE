"""Checklists d’étapes projet — modèles fixes par branche (DT + Assistant)."""

from django.utils import timezone
from django.utils.text import slugify

from .branches import normalize_branch

METAL_CHECKLIST = (
    'Préparation de fichier',
    'Découpe',
    'Ajustage structure',
    'Pose feuille',
    'Peinture auto',
    'Électrostatique',
)

BRANDING_FAMILY_CHECKLIST = (
    'Préparation de fichier',
    'Découpe',
    'Impression',
    'Pose',
    'Finition',
    'Peinture',
    'Autres',
)

# Métal = liste dédiée ; bois / branding / signalétique / gravure / RD = même liste
BRANCH_CHECKLISTS = {
    'metal_design': METAL_CHECKLIST,
    'wood_design': BRANDING_FAMILY_CHECKLIST,
    'branding': BRANDING_FAMILY_CHECKLIST,
    'signaletique': BRANDING_FAMILY_CHECKLIST,
    'gravure': BRANDING_FAMILY_CHECKLIST,
    'design_rd_innovation': BRANDING_FAMILY_CHECKLIST,
}


def checklist_template_for_branch(branch):
    key = normalize_branch(branch)
    return BRANCH_CHECKLISTS.get(key, BRANDING_FAMILY_CHECKLIST)


def step_key(label, index):
    base = slugify(label) or f'step-{index}'
    return f'{index:02d}-{base}'[:80]


def ensure_project_checklist(project, *, reset_if_branch_changed=False):
    """Crée les étapes manquantes selon la branche du projet (idempotent)."""
    from .models import ProjectChecklistItem

    labels = checklist_template_for_branch(project.branch)
    existing = {
        item.key: item
        for item in ProjectChecklistItem.objects.filter(project=project)
    }
    expected_keys = [step_key(label, i) for i, label in enumerate(labels)]

    if reset_if_branch_changed and existing:
        unexpected = set(existing) - set(expected_keys)
        if unexpected or len(existing) != len(expected_keys):
            # Branche changée : on recrée proprement (cases décochées)
            ProjectChecklistItem.objects.filter(project=project).delete()
            existing = {}

    created = 0
    for index, label in enumerate(labels):
        key = step_key(label, index)
        if key in existing:
            item = existing[key]
            if item.label != label or item.order != index:
                item.label = label
                item.order = index
                item.save(update_fields=['label', 'order'])
            continue
        ProjectChecklistItem.objects.create(
            project=project,
            key=key,
            label=label,
            order=index,
        )
        created += 1
    if created and hasattr(project, '_prefetched_objects_cache'):
        project._prefetched_objects_cache.pop('checklist_items', None)
    return created


def project_checklist_stats(project):
    items = list(project.checklist_items.all())
    if not items:
        ensure_project_checklist(project)
        items = list(project.checklist_items.all())
    total = len(items)
    done = sum(1 for item in items if item.is_done)
    percent = int(round((done * 100) / total)) if total else 0
    return {
        'items': items,
        'total': total,
        'done': done,
        'percent': percent,
        'complete': total > 0 and done == total,
        'remaining': [item.label for item in items if not item.is_done],
    }


def is_project_checklist_complete(project):
    return project_checklist_stats(project)['complete']


def checklist_block_message(project):
    stats = project_checklist_stats(project)
    if stats['complete']:
        return ''
    missing = ', '.join(stats['remaining'][:4])
    more = ''
    if len(stats['remaining']) > 4:
        more = f' (+{len(stats["remaining"]) - 4})'
    return (
        f'Checklist incomplète ({stats["done"]}/{stats["total"]}). '
        f'Étapes restantes : {missing}{more}. '
        'Seuls le DT et son Assistant peuvent cocher les étapes.'
    )


def toggle_checklist_item(item, user, *, is_done=None):
    """Bascule ou force l’état d’une étape. Retourne le nouvel état."""
    new_done = (not item.is_done) if is_done is None else bool(is_done)
    item.is_done = new_done
    if new_done:
        item.completed_at = timezone.now()
        item.completed_by = user
    else:
        item.completed_at = None
        item.completed_by = None
    item.save(update_fields=['is_done', 'completed_at', 'completed_by'])
    return item
