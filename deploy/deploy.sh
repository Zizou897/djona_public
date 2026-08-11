#!/usr/bin/env bash
# À lancer sur le VPS après chaque mise à jour du code (git pull).
# Usage : ./deploy/deploy.sh

set -euo pipefail

PROJECT_DIR="/var/www/project/djona_public"
SERVICE_NAME="gunicorn_djona_public.service"

cd "$PROJECT_DIR"

echo "==> git pull"
git pull

echo "==> activation du venv"
source venv/bin/activate

echo "==> dépendances Python"
pip install -r requirements.txt

echo "==> dépendances Node + build Tailwind"
npm ci
npm run build:css

echo "==> migrations Django"
python manage.py migrate --noinput --settings=config.settings.prod

echo "==> collecte des fichiers statiques"
python manage.py collectstatic --noinput --settings=config.settings.prod

echo "==> redémarrage de ${SERVICE_NAME}"
sudo systemctl restart "$SERVICE_NAME"
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "==> déploiement terminé"
