#!/usr/bin/env bash
# Déploie djona_public (marketplace). À lancer sur le VPS après un git pull,
# ou via deploy_all.sh. Usage : sudo bash deploy/deploy_public.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR="/var/www/project/djona_public/public"
SERVICE="gunicorn_djona_public.service"
URL="https://djona.tech/"

cd "$PROJECT_DIR"
source venv/bin/activate

echo "==> [public] dépendances Python"
pip install -q -r requirements.txt

echo "==> [public] dépendances Node + build Tailwind"
npm ci --silent
npm run build:css --silent

echo "==> [public] vérification Django (deploy checklist) AVANT de toucher au service"
python manage.py check --deploy --settings=config.settings.prod

echo "==> [public] migrations"
python manage.py migrate --noinput --settings=config.settings.prod

echo "==> [public] collecte des statiques"
python manage.py collectstatic --noinput --settings=config.settings.prod

restart_and_check "$SERVICE" "$URL" 200

echo "==> [public] déploiement réussi"
