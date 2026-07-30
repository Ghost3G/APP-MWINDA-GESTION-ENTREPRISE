# AppMwinda — Groupe Agence Mwinda

Application Django de gestion d’entreprise (projets, tâches, messages, finance, rapports).

## Mise à jour en production (Render)

Workflow recommandé à chaque évolution :

1. Modifier le code en local
2. Tester (`python manage.py check` / tests)
3. `git add` → `git commit` → `git push` vers GitHub
4. Render détecte le push (`autoDeploy: true`) et redéploie
5. Au démarrage : `migrate` applique les nouvelles tables/colonnes **sans effacer** les données Postgres

### Ce qui est conservé
| Élément | Conservé au redeploy ? |
|---|---|
| Utilisateurs, projets, tâches, messages, finance | **Oui** (Postgres `DATABASE_URL`) |
| Photos / avatars / pièces jointes | **Oui** si `CLOUDINARY_URL` est défini |
| Code source | Remplacé par la nouvelle version |
| Mot de passe admin existant | **Conservé** (plus de reset à chaque deploy) |

### Variables d’environnement obligatoires (Render)
- `DEBUG=False`
- `SECRET_KEY` (généré)
- `DATABASE_URL` (lié au Postgres Render)
- `DATABASE_SSL_REQUIRE=True`
- `CLOUDINARY_URL` (compte Cloudinary gratuit possible)
- `ALLOWED_HOSTS=.onrender.com` (ou votre domaine)
- `ADMIN_PASSWORD` (uniquement utile au **premier** démarrage)

### Premier déploiement
1. Créer le service via `render.yaml` (web + Postgres)
2. Dans le dashboard Render, renseigner :
   - `CLOUDINARY_URL`
   - `ADMIN_PASSWORD` (fort)
3. Déployer — migrations + admin créés une fois
4. Se connecter et changer le mot de passe si besoin

### Développement local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis adapter
python manage.py migrate
python manage.py runserver
```

Localement sans `DATABASE_URL` → SQLite (`db.sqlite3`).  
En prod Render → toujours Postgres.

### Checklist sécurité production
- [ ] `DEBUG=False`
- [ ] `SECRET_KEY` forte (générée Render, jamais la clé `django-insecure-…`)
- [ ] `CLOUDINARY_URL` renseigné (médias durables)
- [ ] `ADMIN_PASSWORD` fort au 1er démarrage, puis changé dans l’app
- [ ] Ne pas exécuter `seed_demo_data.py` en prod
- [ ] `/setup/` bloqué sauf `SETUP_TOKEN` (optionnel)
- [ ] Endpoints debug absents hors `DEBUG=True`

### Structure
- `AppMwinda/` — configuration
- `users/` — comptes, sécurité, notifications
- `projects/` — projets, tâches, tableau Kanban
- `messaging/` — messagerie
- `reports/` — rapports & finance
- `scripts/render_start.sh` — démarrage prod (wait DB → migrate → gunicorn)

### Sauvegardes
- **Prod** : utiliser les backups Postgres Render (dashboard)
- **Local SQLite** : `./scripts/backup_db.sh`
