"""
Corrige uniquement les noms / titres affichés de 4 agents.
Ne touche PAS : username, mot de passe, rôle, org_group, droits.

Usage Render Shell :
  python manage.py ensure_agent_display_names
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

# Identifiants inchangés → sessions actives conservées
DISPLAY_FIXES = {
    'paul.mayubu': {
        'first_name': 'Paul',
        'last_name': 'Mayambo',
        'job_title': 'Technicien & Contrôle qualités',
        'grade': 'TECHNICIEN',
        'department_name': 'Direction Techniques',
    },
    'remedi.samba': {
        'first_name': 'Remedi',
        'last_name': 'Samba',
        'job_title': 'Technicien Expert en Peinture',
        'grade': 'TECHNICIEN',
        'department_name': 'Direction Techniques',
    },
    'nehemie.musafiri': {
        'first_name': 'Nehemie',
        'last_name': 'Musafiri',
        'job_title': 'Technicien 3D et Branding',
        'grade': 'TECHNICIEN',
        'department_name': 'Direction Techniques',
    },
    'joel.kabale': {
        'first_name': 'Joel Ray',
        'last_name': 'Kalenga',
        'job_title': 'Designer Graphique et Community Manager',
        'grade': 'DESIGNER',
        'department_name': 'Design et Communication',
    },
}


class Command(BaseCommand):
    help = "Corrige les noms/titres affichés (sans changer accès ni mots de passe)."

    def handle(self, *args, **options):
        for username, fields in DISPLAY_FIXES.items():
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.WARNING(f'[SKIP] Compte introuvable : {username}'))
                continue

            changed = []
            for field, value in fields.items():
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)

            if changed:
                user.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] {username} → {user.get_labeled_name()} '
                    f'(champs : {", ".join(changed)})'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Déjà à jour : {user.get_labeled_name()} ({username})'
                ))

        self.stdout.write(
            'Accès / identifiants / mots de passe inchangés — sessions conservées.'
        )
