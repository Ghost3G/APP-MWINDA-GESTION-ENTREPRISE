# AppMwinda

Application Django pour la gestion de projets et rapports.

## Déploiement sur Render

### Prérequis
- Compte Render (render.com)
- Repository GitHub/GitLab avec ce code

### Étapes de déploiement

1. **Push vers Git** :
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Render deployment"
   git branch -M main
   git remote add origin https://github.com/your-username/your-repo.git
   git push -u origin main
   ```

2. **Déploiement sur Render** :
   - Connectez votre repository à Render
   - Render détectera automatiquement le fichier `render.yaml`
   - La base de données PostgreSQL sera créée automatiquement

3. **Configuration des variables d'environnement** :
   Dans les settings de votre service Render, ajoutez :
   - `ALLOWED_HOSTS` : votre-domaine.onrender.com (ex: appmwinda.onrender.com)

4. **Après déploiement** :
   - L'application sera accessible à l'URL fournie par Render
   - Pour créer un superuser : `python manage.py createsuperuser`

### Variables d'environnement
- `DEBUG` : False (configuré automatiquement)
- `SECRET_KEY` : Généré automatiquement par Render
- `DATABASE_URL` : Fourni automatiquement par Render
- `ALLOWED_HOSTS` : À configurer dans les secrets Render

### Développement local

1. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

2. Configurez votre `.env` basé sur `.env.example`

3. Migrez la base de données :
   ```bash
   python manage.py migrate
   ```

4. Lancez le serveur :
   ```bash
   python manage.py runserver
   ```

### Structure du projet
- `AppMwinda/` : Configuration Django
- `users/` : Gestion des utilisateurs
- `projects/` : Gestion des projets
- `messaging/` : Système de messagerie
- `reports/` : Génération de rapports
- `static/` : Fichiers statiques
- `templates/` : Templates HTML

## Sécurité (Phase 1)

- Verrouillage login après 5 échecs sur 15 minutes.
- Durcissement mot de passe (minimum 10 caractères + validateurs Django).
- Expiration de session renforcée (8h, fermeture navigateur, cookie HTTPOnly).
- Journal d'audit minimal (`users.AuditLog`) pour actions HTTP sensibles.

## Sauvegarde et restauration (SQLite)

Créer un backup:

```bash
./scripts/backup_db.sh
```

Restaurer un backup:

```bash
./scripts/restore_db.sh backups/db_YYYYMMDD_HHMMSS.sqlite3.gz
```

Note: arrêter le serveur avant restauration.