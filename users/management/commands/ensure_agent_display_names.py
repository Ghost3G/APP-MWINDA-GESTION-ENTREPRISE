"""
Corrige uniquement les noms / titres affichés de 4 agents.
Ne touche PAS : username, mot de passe, rôle, org_group, droits.

Usage Render Shell :
  python manage.py ensure_agent_display_names
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Q


# Identifiant principal + alias éventuels (prod / anciennes versions)
DISPLAY_FIXES = (
    {
        'usernames': ('paul.mayubu', 'paul.mayambo'),
        'match_names': (('Paul', 'Mayubu'), ('Paul', 'Mayambo')),
        'fields': {
            'first_name': 'Paul',
            'last_name': 'Mayambo',
            'job_title': 'Technicien & Controle qualites',
            'grade': 'TECHNICIEN',
            'department_name': 'Direction Techniques',
        },
        'display_title': 'Technicien & Contrôle qualités',
    },
    {
        'usernames': ('remedi.samba',),
        'match_names': (('Remedi', 'Samba'),),
        'fields': {
            'first_name': 'Remedi',
            'last_name': 'Samba',
            'job_title': 'Technicien Expert en Peinture',
            'grade': 'TECHNICIEN',
            'department_name': 'Direction Techniques',
        },
        'display_title': 'Technicien Expert en Peinture',
    },
    {
        'usernames': ('nehemie.musafiri',),
        'match_names': (('Nehemie', 'Musafiri'),),
        'fields': {
            'first_name': 'Nehemie',
            'last_name': 'Musafiri',
            'job_title': 'Technicien 3D et Branding',
            'grade': 'TECHNICIEN',
            'department_name': 'Direction Techniques',
        },
        'display_title': 'Technicien 3D et Branding',
    },
    {
        'usernames': ('joel.kabale', 'joel.kalenga'),
        'match_names': (('Joel', 'Kalenga'), ('Joel Ray', 'Kalenga')),
        'fields': {
            'first_name': 'Joel Ray',
            'last_name': 'Kalenga',
            'job_title': 'Designer Graphique et Community Manager',
            'grade': 'DESIGNER',
            'department_name': 'Design et Communication',
        },
        'display_title': 'Designer Graphique et Community Manager',
    },
)


class Command(BaseCommand):
    help = "Corrige les noms/titres affichés (sans changer accès ni mots de passe)."

    def _find_user(self, User, entry):
        for username in entry['usernames']:
            user = User.objects.filter(username__iexact=username).first()
            if user:
                return user

        query = Q()
        for first_name, last_name in entry['match_names']:
            query |= Q(first_name__iexact=first_name, last_name__iexact=last_name)
        return User.objects.filter(query).order_by('id').first()

    def handle(self, *args, **options):
        User = get_user_model()
        updated = 0
        skipped = 0

        for entry in DISPLAY_FIXES:
            fields = dict(entry['fields'])
            # Affichage avec accents (si la DB/UTF-8 le permet)
            fields['job_title'] = entry['display_title']

            user = self._find_user(User, entry)
            if not user:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"[SKIP] Compte introuvable pour {entry['usernames'][0]}"
                ))
                continue

            changed = []
            for field, value in fields.items():
                if not hasattr(user, field):
                    continue
                if getattr(user, field) != value:
                    setattr(user, field, value)
                    changed.append(field)

            if changed:
                user.save(update_fields=changed)
                updated += 1
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] {user.username} -> {user.get_labeled_name()} '
                    f'(champs: {", ".join(changed)})'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'[OK] Deja a jour: {user.get_labeled_name()} ({user.username})'
                ))

        self.stdout.write(
            f'Termine. Mis a jour: {updated}. Introuvables: {skipped}. '
            'Acces / identifiants / mots de passe inchanges.'
        )
