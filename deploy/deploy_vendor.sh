#!/usr/bin/env bash
# Déploie le projet vendor (espace vendeur). À lancer sur le VPS après un git
# pull, ou via deploy_all.sh. Usage : sudo bash deploy/deploy_vendor.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR="/var/www/project/djona_public/vendor/core"
SERVICE="gunicorn_djona_vendor.service"
URL="https://vendor.djona.tech/"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "==> [vendor] dépendances Python"
pip install -q -r requirements.txt

cd src

echo "==> [vendor] vérification Django (deploy checklist) AVANT de toucher au service"
python manage.py check --deploy

echo "==> [vendor] migrations"
python manage.py migrate --noinput

echo "==> [vendor] collecte des statiques"
python manage.py collectstatic --noinput

# Le cache fichiers (limitation des tentatives de connexion) doit appartenir à l'utilisateur de
# gunicorn : créé par root, il est inutilisable par le service (la limitation serait alors ignorée).
echo "==> [vendor] droits du cache fichiers"
mkdir -p cache_framework
chown -R www-data:www-data cache_framework

# / redirige vers /connexion/ pour un visiteur non authentifié — c'est le
# comportement normal, pas une panne.
restart_and_check "$SERVICE" "$URL" 200 302

echo "==> [vendor] déploiement réussi"
