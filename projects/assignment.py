"""
Affectation intelligente des tâches projet.

1) Tentative IA (si OPENAI_API_KEY) pour proposer un plan selon projet + titres agents
2) Sinon / en secours : règles métier (branche, org_group, job_title, charge)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections import Counter

from django.contrib.auth import get_user_model

from .branches import normalize_branch, get_branch_label
from .task_services import (
    create_project_task,
    get_templates_for_department,
    resolve_task_branch,
)

User = get_user_model()

# Mots-clés tâche → profils ciblés
TASK_KEYWORD_PROFILES = (
    (('commercial', 'client', 'brief branding', 'validation client', 'devis commercial'), ('commercial',)),
    (('finance', 'facture', 'budget', 'comptable', 'paiement'), ('finance',)),
    (('logistique', 'livraison', 'emballage', 'transport'), ('logistique',)),
    (('metal', 'soudure', 'laser', 'plasma', 'pliage', 'structure'), ('metal_design', 'technique')),
    (('bois', 'wood', 'cnc', 'vernis', 'menuiser'), ('wood_design', 'technique')),
    (('branding', 'identité', 'graphique', 'créatif', 'assets'), ('branding', 'design_communication')),
    (('signalétique', 'signaletique', 'panneau', 'pose'), ('signaletique', 'technique')),
    (('gravure', 'laser gravure', 'profondeur'), ('gravure', 'technique')),
    (('prototype', 'r&d', 'innovation', 'recherche', 'matériau'), ('design_rd_innovation', 'rd')),
    (('qualité', 'contrôle', 'clôture'), ('technique', 'metal_design', 'wood_design')),
)


def _text_blob(user):
    parts = [
        getattr(user, 'job_title', '') or '',
        getattr(user, 'grade', '') or '',
        getattr(user, 'department_name', '') or '',
        getattr(user, 'org_group', '') or '',
        getattr(user, 'direction', '') or '',
        user.get_title_label() if hasattr(user, 'get_title_label') else '',
        user.get_display_name() if hasattr(user, 'get_display_name') else '',
    ]
    return ' '.join(parts).lower()


def _profiles_for_task(title: str):
    title_l = (title or '').lower()
    profiles = []
    for keywords, profs in TASK_KEYWORD_PROFILES:
        if any(k in title_l for k in keywords):
            profiles.extend(profs)
    return tuple(dict.fromkeys(profiles))


def _score_agent_for_task(user, title, project_branch, workload):
    score = 0
    blob = _text_blob(user)
    profiles = _profiles_for_task(title)
    user_direction = normalize_branch(getattr(user, 'direction', None) or '')
    org = (getattr(user, 'org_group', '') or '').lower()

    if user_direction == project_branch:
        score += 40
    if project_branch and project_branch.replace('_', ' ') in blob:
        score += 15
    if get_branch_label(project_branch).lower() in blob:
        score += 10

    for profile in profiles:
        if profile == org:
            score += 35
        if profile == user_direction:
            score += 25
        if profile.replace('_', ' ') in blob or profile in blob:
            score += 20

    # Agents techniques génériques
    if org in {'technique', 'rd', 'design_communication'} and not profiles:
        score += 8
    if org == 'commercial' and any(p == 'commercial' for p in profiles):
        score += 30
    if org == 'finance' and any(p == 'finance' for p in profiles):
        score += 30

    # Pénaliser la surcharge
    score -= min(workload.get(user.id, 0) * 3, 25)

    # Préférer les agents au role agent
    if getattr(user, 'role', '') == 'agent':
        score += 5
    if getattr(user, 'role', '') == 'directeur':
        score -= 5

    return score


def build_rules_plan(project, members=None):
    """Plan d'affectation par règles métier."""
    members = list(members if members is not None else project.members.filter(is_active=True))
    if not members:
        return [], 'rules'

    branch = normalize_branch(getattr(project, 'branch', None) or 'metal_design')
    titles = list(get_templates_for_department(branch))

    # Tâches transverses utiles selon composition d'équipe
    orgs = {getattr(m, 'org_group', '') for m in members}
    if 'commercial' in orgs and 'Brief commercial / suivi client' not in titles:
        titles.insert(0, 'Brief commercial / suivi client')
    if 'finance' in orgs and 'Suivi budget / devis projet' not in titles:
        titles.append('Suivi budget / devis projet')

    workload = Counter(
        project.tasks.filter(assigned_to__in=members)
        .exclude(status='done')
        .values_list('assigned_to_id', flat=True)
    )

    plan = []
    for title in titles:
        ranked = sorted(
            members,
            key=lambda user: _score_agent_for_task(user, title, branch, workload),
            reverse=True,
        )
        best = ranked[0]
        best_score = _score_agent_for_task(best, title, branch, workload)
        # Si score trop faible, privilégier un agent de la branche projet
        if best_score < 10:
            branch_mates = [m for m in members if normalize_branch(getattr(m, 'direction', None) or '') == branch]
            if branch_mates:
                best = min(branch_mates, key=lambda m: workload.get(m.id, 0))
        plan.append({
            'title': title,
            'user': best,
            'username': best.username,
            'reason': 'Règles métier (titre / département / charge)',
            'department': resolve_task_branch(project, best, branch),
        })
        workload[best.id] += 1

    return plan, 'rules'


def _openai_enabled():
    return bool(os.environ.get('OPENAI_API_KEY', '').strip())


def _call_openai_plan(project, members, template_titles):
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini').strip() or 'gpt-4o-mini'
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY manquante')

    agents_payload = [
        {
            'username': m.username,
            'name': m.get_labeled_name() if hasattr(m, 'get_labeled_name') else m.get_display_name(),
            'role': m.get_role_display() if hasattr(m, 'get_role_display') else m.role,
            'title': m.get_title_label() if hasattr(m, 'get_title_label') else (m.job_title or ''),
            'org_group': m.org_group,
            'direction': m.direction,
            'grade': m.grade or '',
        }
        for m in members
    ]
    prompt = {
        'project': {
            'name': project.name,
            'description': project.description or '',
            'branch': getattr(project, 'branch', ''),
            'branch_label': get_branch_label(getattr(project, 'branch', '') or ''),
        },
        'agents': agents_payload,
        'suggested_task_titles': template_titles,
        'instructions': (
            'Propose un plan de tâches pour ce projet Mwinda. '
            'Assigne chaque tâche à UN username de la liste agents uniquement. '
            'Adapte le processus au métier/titre de chaque personne. '
            'Tu peux ajuster les titres si utile, max 12 tâches. '
            'Réponds UNIQUEMENT en JSON: '
            '{"tasks":[{"title":"...","username":"...","reason":"..."}]}'
        ),
    }

    body = json.dumps({
        'model': model,
        'temperature': 0.2,
        'response_format': {'type': 'json_object'},
        'messages': [
            {
                'role': 'system',
                'content': (
                    'Tu es un chef de projet pour Agence Mwinda (signalétique, métal, bois, branding). '
                    'Tu répartis le travail selon les compétences et titres des agents.'
                ),
            },
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=body,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        payload = json.loads(resp.read().decode('utf-8'))

    content = payload['choices'][0]['message']['content']
    data = json.loads(content)
    tasks = data.get('tasks') or []
    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError('Réponse IA vide')

    by_username = {m.username: m for m in members}
    branch = normalize_branch(getattr(project, 'branch', None) or 'metal_design')
    plan = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '').strip()
        username = str(item.get('username') or '').strip()
        reason = str(item.get('reason') or 'Suggestion IA').strip()
        user = by_username.get(username)
        if not title or not user:
            continue
        plan.append({
            'title': title[:200],
            'user': user,
            'username': user.username,
            'reason': reason[:240],
            'department': resolve_task_branch(project, user, branch),
        })
    if not plan:
        raise RuntimeError('Aucun item IA valide')
    return plan


def build_assignment_plan(project, use_ai=True, members=None):
    """
    Construit le plan d'affectation.
    Retourne (plan, source) où source ∈ {'ai', 'rules', 'ai+rules'}.
    """
    members = list(members if members is not None else project.members.filter(is_active=True))
    if not members:
        return [], 'rules'

    branch = normalize_branch(getattr(project, 'branch', None) or 'metal_design')
    template_titles = list(get_templates_for_department(branch))

    if use_ai and _openai_enabled():
        try:
            ai_plan = _call_openai_plan(project, members, template_titles)
            return ai_plan, 'ai'
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, KeyError, ValueError, RuntimeError, json.JSONDecodeError):
            rules_plan, _ = build_rules_plan(project, members=members)
            return rules_plan, 'rules'  # secours

    return build_rules_plan(project, members=members)


def apply_smart_project_plan(project, actor=None, use_ai=True, replace_empty_only=False):
    """
    Applique le plan (IA puis règles) dans Suivi des tâches.
    N'écrase pas les tâches existantes de même titre.
    """
    existing_count = project.tasks.count()
    if replace_empty_only and existing_count > 0:
        return {
            'created': 0,
            'source': 'skipped',
            'message': 'Le projet a déjà des tâches.',
            'plan': [],
        }

    plan, source = build_assignment_plan(project, use_ai=use_ai)
    created = 0
    created_items = []
    existing_titles = set(project.tasks.values_list('title', flat=True))

    for item in plan:
        title = item['title']
        if title in existing_titles:
            continue
        task = create_project_task(
            project,
            item['user'],
            title,
            department=item.get('department'),
            actor=actor,
            notify=True,
        )
        existing_titles.add(title)
        created += 1
        created_items.append({
            'title': task.title,
            'assignee': item['user'].get_labeled_name() if hasattr(item['user'], 'get_labeled_name') else item['username'],
            'reason': item.get('reason', ''),
            'source': source,
        })

    return {
        'created': created,
        'source': source,
        'plan': created_items,
        'message': (
            f"{created} tâche(s) planifiée(s) via {'IA' if source == 'ai' else 'règles métier'}."
            if created else
            'Aucune nouvelle tâche à créer (plan déjà couvert).'
        ),
    }


def ai_available():
    return _openai_enabled()
