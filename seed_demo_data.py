"""
Initialise le personnel MWINDA (noms réels) + projets de simulation.

Source : Tableau du personnel MWINDA (PDF)

Usage:
    source .venv/bin/activate
    python seed_demo_data.py
"""
import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AppMwinda.settings')
django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from projects.models import Project, ProjectTask
from projects.task_services import ensure_project_tasks, set_task_status

# Protection : ne jamais seed les mots de passe démo en production
if not settings.DEBUG and os.environ.get('ALLOW_DEMO_SEED', '').lower() not in {'1', 'true', 'yes'}:
    raise SystemExit(
        "seed_demo_data refusé en production (DEBUG=False). "
        "Pour forcer localement : ALLOW_DEMO_SEED=1"
    )

User = get_user_model()

# Ne jamais inclure 'admin' : compte prod créé au déploiement Render.
LEGACY_USERNAMES = [
    'directeur',
    'agent_metal',
    'agent_wood',
    'agent_branding',
    'agent_signaletique',
    'agent_gravure',
    'agent_rd',
    'agent_design',
    'agent_finance',
    'agent_marketing',
    'agent_technique',
]

DIRECTOR_GRADES = {
    'DIRECTEUR GENERAL',
    'DIRECTEUR FINANCIER',
    'DIRECTEUR TECHNIQUE',
    'ASSISTANT DIRECTEUR TECHNIQUE',
    'ASSISTANT DIRECTEUR FINANCIER',
}

# Directeurs (leadership) — Hans (Comptable) est au département Finance
DIRECTOR_USERNAMES = {
    'michael.ilunga',
    'archirey.muhongaya',
    'ibrahim.japhete',
    'emmanuel.maki',
}

PERSONNEL = [
    {
        'username': 'michael.ilunga',
        'first_name': 'Michael',
        'last_name': 'Kabale Ilunga',
        'function': 'Directeur Général',
        'department': 'Direction Général',
        'grade': 'DIRECTEUR GENERAL',
        'direction': 'design_rd_innovation',
        'password': 'Ilunga2026',
        'is_superuser': True,
        'is_staff': True,
    },
    {
        'username': 'archirey.muhongaya',
        'first_name': 'Archirey',
        'last_name': 'Mowunga',
        'function': 'Directeur Financier et Administratif',
        'department': 'Direction Administratif et Financier',
        'grade': 'DIRECTEUR FINANCIER',
        'direction': 'design_rd_innovation',
        'password': 'Muhongaya2026',
    },
    {
        'username': 'ibrahim.japhete',
        'first_name': 'Japhete',
        'last_name': 'Kuta',
        'function': 'Directeur Technique',
        'department': 'Direction Techniques',
        'grade': 'DIRECTEUR TECHNIQUE',
        'direction': 'metal_design',
        'password': 'Japhete2026',
    },
    {
        'username': 'emmanuel.maki',
        'first_name': 'Emmanuel',
        'last_name': 'Maki',
        'function': 'Ass. Directeur Technique et Responsable Production',
        'department': 'Direction Techniques',
        'grade': 'ASSISTANT DIRECTEUR TECHNIQUE',
        'direction': 'metal_design',
        'password': 'Maki2026',
    },
    {
        'username': 'hans.mangi',
        'first_name': 'Hans',
        'last_name': 'Kabasele',
        'function': 'Comptable',
        'department': 'Direction Administratif et Financier',
        'grade': 'COMPTABLE',
        'direction': 'design_rd_innovation',
        'password': 'Mangi2026',
        'org_group': 'finance',
    },
    {
        'username': 'joseph.mbuyu',
        'first_name': 'Joseph',
        'last_name': 'Mbuyu',
        'function': 'Agent Logistique',
        'department': 'Logistique',
        'grade': 'AGENT',
        'direction': 'metal_design',
        'password': 'Mbuyu2026',
        'org_group': 'logistique',
    },
    {
        'username': 'huges.phebe',
        'first_name': 'Hugue',
        'last_name': 'Phebe',
        'function': 'Designer',
        'department': 'Design et Communication',
        'grade': 'DESIGNER',
        'direction': 'branding',
        'password': 'Phebe2026',
        'org_group': 'design_communication',
    },
    {
        'username': 'christenvie.bitumba',
        'first_name': 'Christenvie',
        'last_name': 'Besomono Bitumba',
        'function': 'Architecte Intérieurs',
        'department': 'Direction Techniques',
        'grade': 'AGENT',
        'direction': 'wood_design',
        'password': 'Bitumba2026',
    },
    {
        'username': 'chrinovic.kabale',
        'first_name': 'Chrinovic',
        'last_name': 'Kabale',
        'function': 'Stagiaires',
        'department': 'Recherche et Développement',
        'grade': 'DESIGNER',
        'direction': 'design_rd_innovation',
        'password': 'Kabale2026',
        'org_group': 'rd',
    },
    {
        'username': 'louise.netando',
        'first_name': 'Louise',
        'last_name': "Baruani N'etando",
        'function': 'Électronicienne',
        'department': 'Recherche et Développement',
        'grade': 'TECHNICIENNE',
        'direction': 'design_rd_innovation',
        'password': 'Netando2026',
        'org_group': 'rd',
    },
    {
        'username': 'joel.kabale',
        'first_name': 'Joel',
        'last_name': 'Kalenga',
        'function': 'Designer',
        'department': 'Design et Communication',
        'grade': 'DESIGNER',
        'direction': 'branding',
        'password': 'Joel2026',
        'org_group': 'design_communication',
    },
    {
        'username': 'flori.mata',
        'first_name': 'Flori',
        'last_name': 'Mata',
        'function': 'Technicien',
        'department': 'Direction Techniques',
        'grade': 'TECHNICIEN',
        'direction': 'metal_design',
        'password': 'Mata2026',
    },
    {
        'username': 'paul.mayubu',
        'first_name': 'Paul',
        'last_name': 'Mayubu',
        'function': 'Technicien',
        'department': 'Direction Techniques',
        'grade': 'TECHNICIEN',
        'direction': 'metal_design',
        'password': 'Mayubu2026',
    },
    {
        'username': 'nehemie.musafiri',
        'first_name': 'Nehemie',
        'last_name': 'Musafiri',
        'function': 'Technicien',
        'department': 'Direction Techniques',
        'grade': 'TECHNICIEN',
        'direction': 'metal_design',
        'password': 'Musafiri2026',
    },
    {
        'username': 'remedi.samba',
        'first_name': 'Remedi',
        'last_name': 'Samba',
        'function': 'Technicien',
        'department': 'Direction Techniques',
        'grade': 'TECHNICIEN',
        'direction': 'metal_design',
        'password': 'Samba2026',
    },
    {
        'username': 'nevile.isako',
        'first_name': 'Nevile',
        'last_name': 'Isako',
        'function': 'Technicien Ajusteur',
        'department': 'Direction Techniques',
        'grade': 'TECHNICIEN',
        'direction': 'metal_design',
        'password': 'Isako2026',
    },
    {
        'username': 'rachel.nsilulu',
        'first_name': 'Rachel',
        'last_name': 'Kiesolo Nsilulu',
        'function': 'Agent Commercial',
        'department': 'Direction Commercial',
        'grade': 'Agent Commercial',
        'direction': 'branding',
        'password': 'Nsilulu2026',
    },
    {
        'username': 'jemima.faila',
        'first_name': 'Jemima',
        'last_name': 'Beloko Faila',
        'function': 'Agent Commercial',
        'department': 'Direction Commercial',
        'grade': 'Agent Commercial',
        'direction': 'branding',
        'password': 'Faila2026',
    },
    {
        'username': 'christian.lisimo',
        'first_name': 'Christian',
        'last_name': 'Lisimo',
        'function': 'Agent Commercial',
        'department': 'Direction Commercial',
        'grade': 'Agent Commercial',
        'direction': 'branding',
        'password': 'Lisimo2026',
    },
    {
        'username': 'cesar.kyabuta',
        'first_name': 'Cesar',
        'last_name': 'Kyabuta',
        'function': 'Agent Commercial',
        'department': 'Direction Commercial',
        'grade': 'Agent Commercial',
        'direction': 'branding',
        'password': 'Kyabuta2026',
    },
]


def role_for_grade(grade, person):
    if person.get('username') in DIRECTOR_USERNAMES:
        if person.get('is_superuser'):
            return 'admin'
        return 'directeur'
    if person.get('is_superuser'):
        return 'admin'
    if grade in DIRECTOR_GRADES:
        return 'directeur'
    return 'agent'


def org_group_for_person(person):
    if person.get('org_group'):
        return person['org_group']
    if person.get('username') in DIRECTOR_USERNAMES or person.get('is_superuser'):
        return 'direction'

    department = (person.get('department') or '').lower()
    function = (person.get('function') or '').lower()
    grade = (person.get('grade') or '').lower()

    if 'comptable' in function or 'comptable' in grade or 'financier' in department:
        return 'finance'
    if 'commercial' in department or 'commercial' in function:
        return 'commercial'
    if 'logistique' in department or 'logistique' in function:
        return 'logistique'
    if 'designer' in grade or 'designer' in function or 'graphiste' in function or 'community' in function:
        return 'design_communication'
    if 'innovation' in function or 'recherche' in function or 'développement' in function:
        return 'rd'
    return 'technique'


def slug_email(username):
    return f'{username}@agencemwinda.com'


def upsert_user(data):
    grade = data['grade']
    role = role_for_grade(grade, data)

    user, created = User.objects.get_or_create(
        username=data['username'],
        defaults={
            'email': slug_email(data['username']),
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'role': role,
            'org_group': org_group_for_person(data),
            'direction': data['direction'],
            'is_staff': data.get('is_staff', role == 'admin'),
            'is_superuser': data.get('is_superuser', False),
        },
    )
    user.email = slug_email(data['username'])
    user.first_name = data['first_name']
    user.last_name = data['last_name']
    user.role = role
    user.org_group = org_group_for_person(data)
    user.direction = data['direction']
    user.job_title = data['function']
    user.grade = grade
    user.department_name = data['department']
    user.is_staff = data.get('is_staff', role == 'admin')
    user.is_superuser = data.get('is_superuser', False)
    user.set_password(data['password'])
    user.save()
    return user, created


def remove_legacy_users():
    deleted, _ = User.objects.filter(username__in=LEGACY_USERNAMES).delete()
    if deleted:
        print(f'Comptes génériques supprimés : {deleted} enregistrement(s).')


def seed_projects(users_by_username):
    today = date.today()
    ibrahim = users_by_username['ibrahim.japhete']
    emmanuel = users_by_username['emmanuel.maki']

    projects_data = [
        {
            'name': 'Showroom MWINDA — Signalétique',
            'description': 'Aménagement signalétique et identité visuelle du showroom MWINDA.',
            'branch': 'signaletique',
            'technical_director': ibrahim,
            'manager': emmanuel,
            'commercial_agent': users_by_username['rachel.nsilulu'],
            'execution_members': [
                users_by_username['huges.phebe'],
                users_by_username['christenvie.bitumba'],
                users_by_username['joel.kabale'],
                users_by_username['chrinovic.kabale'],
            ],
        },
        {
            'name': 'Hall Expo — Structure Métal',
            'description': 'Fabrication et installation de la structure métallique pour le hall expo.',
            'branch': 'metal_design',
            'technical_director': ibrahim,
            'manager': emmanuel,
            'commercial_agent': users_by_username['christian.lisimo'],
            'execution_members': [
                users_by_username['flori.mata'],
                users_by_username['paul.mayubu'],
                users_by_username['nehemie.musafiri'],
                users_by_username['remedi.samba'],
                users_by_username['nevile.isako'],
                users_by_username['louise.netando'],
            ],
        },
    ]

    for project_data in projects_data:
        project, created = Project.objects.get_or_create(
            name=project_data['name'],
            defaults={
                'description': project_data['description'],
                'start_date': today - timedelta(days=5),
                'end_date': today + timedelta(days=25),
                'status': 'progress',
                'branch': project_data['branch'],
                'manager': project_data['manager'],
                'technical_director': project_data['technical_director'],
                'commercial_agent': project_data['commercial_agent'],
            },
        )
        if not created:
            project.description = project_data['description']
            project.branch = project_data['branch']
            project.manager = project_data['manager']
            project.technical_director = project_data['technical_director']
            project.commercial_agent = project_data['commercial_agent']
            project.status = 'progress'
            project.save()

        all_members = list(project_data['execution_members'])
        for stakeholder in (
            project_data['technical_director'],
            project_data['manager'],
            project_data['commercial_agent'],
        ):
            if stakeholder and stakeholder not in all_members:
                all_members.append(stakeholder)

        project.members.set(all_members)
        ensure_project_tasks(project)

        for member_index, member in enumerate(project_data['execution_members']):
            user_tasks = list(
                ProjectTask.objects.filter(project=project, assigned_to=member).order_by('order')
            )
            done_count = min(1 + member_index, len(user_tasks))
            for task in user_tasks[:done_count]:
                set_task_status(task, 'done')
            if done_count < len(user_tasks):
                set_task_status(user_tasks[done_count], 'in_progress')

        action = 'créé' if created else 'mis à jour'
        print(f'Projet {action} : {project.name}')
        print(f'  → Directeur Technique : {project.technical_director.get_full_name()}')
        print(f'  → Responsable suivi   : {project.manager.get_full_name()}')
        print(f'  → Agent commercial    : {project.commercial_agent.get_full_name()}')


def main():
    remove_legacy_users()

    users_by_username = {}
    directors = []
    agents = []

    print('\n=== Personnel MWINDA (tableau officiel) ===')
    for person in PERSONNEL:
        user, created = upsert_user(person)
        users_by_username[person['username']] = user
        status = 'créé' if created else 'mis à jour'
        access = 'ACCÈS COMPLET' if user.role in ['admin', 'directeur'] else 'ACCÈS LIMITÉ'
        print(f"[{status}] {user.get_full_name()}")
        print(f"         Fonction    : {person['function']}")
        print(f"         Département : {person['department']}")
        print(f"         Mention     : {person['grade']}")
        print(f"         Département : {user.get_org_group_display()}")
        print(f"         Email       : {slug_email(person['username'])}")
        print(f"         Identifiant : {person['username']}")
        print(f"         Mot de passe: {person['password']}")
        print(f"         Rôle app    : {user.get_role_display()} ({access})")
        print()

        if user.role in ['admin', 'directeur']:
            directors.append(user)
        else:
            agents.append(user)

    seed_projects(users_by_username)

    print('\n=== Récapitulatif ===')
    print(f'Directeurs / Admin (accès complet) : {len(directors)}')
    print(f'Agents (accès limité)              : {len(agents)}')
    print(f'Projets de simulation              : 2')


if __name__ == '__main__':
    main()
