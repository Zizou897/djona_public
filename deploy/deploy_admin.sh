#!/usr/bin/env bash
# Déploie le projet admin (back-office). À lancer sur le VPS après un git pull,
# ou via deploy_all.sh. Usage : sudo bash deploy/deploy_admin.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR="/var/www/project/djona_public/admin/core"
SERVICE="gunicorn_djona_admin.service"
URL="https://admin.djona.tech/"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "==> [admin] dépendances Python"
pip install -q -r requirements.txt

cd src

echo "==> [admin] vérification Django (deploy checklist) AVANT de toucher au service"
python manage.py check --deploy

echo "==> [admin] migrations"
python manage.py migrate --noinput

echo "==> [admin] collecte des statiques"
python manage.py collectstatic --noinput

# Les photos de pièces envoyées depuis le back-office sont écrites dans le
# media_cdn du projet public (servi par le site) : media_cdn/parts doit y pointer.
echo "==> [admin] lien média Djona Parts"
PUBLIC_PARTS="/var/www/project/djona_public/public/media_cdn/parts"
mkdir -p "$PUBLIC_PARTS" media_cdn
chown www-data:www-data "$PUBLIC_PARTS"
ln -sfn "$PUBLIC_PARTS" media_cdn/parts

# Le cache fichiers (limitation des tentatives de connexion) doit appartenir à l'utilisateur de
# gunicorn : créé par root, il est inutilisable par le service (la limitation serait alors ignorée).
echo "==> [admin] droits du cache fichiers"
mkdir -p cache_framework
chown -R www-data:www-data cache_framework

restart_and_check "$SERVICE" "$URL" 200 302

echo "==> [admin] déploiement réussi"
