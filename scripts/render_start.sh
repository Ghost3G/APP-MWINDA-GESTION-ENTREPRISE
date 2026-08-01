#!/usr/bin/env bash
# Script de démarrage Render — migrations sûres + données Postgres conservées
set -euo pipefail

echo "[release] Attente base de données..."
python manage.py wait_for_db --timeout 120

echo "[release] Application des migrations (données existantes conservées)..."
python manage.py migrate --noinput

echo "[release] Vérification compte admin (sans écraser le mot de passe)..."
python manage.py create_admin

# Optionnel : une seule fois, mettre ALLOW_DEMO_SEED=1 dans Render Environment puis redeploy,
# puis retirer la variable (évite de réécrire les mots de passe à chaque deploy).
if [ "${ALLOW_DEMO_SEED:-}" = "1" ] || [ "${ALLOW_DEMO_SEED:-}" = "true" ] || [ "${ALLOW_DEMO_SEED:-}" = "yes" ]; then
  echo "[release] Seed personnel MWINDA (ALLOW_DEMO_SEED actif)..."
  python manage.py seed_personnel --force
fi

echo "[release] Démarrage Gunicorn..."
exec gunicorn AppMwinda.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120
