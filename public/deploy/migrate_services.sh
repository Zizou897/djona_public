#!/usr/bin/env bash
# Bascule le VPS de l'ancien service gunicorn/site nginx (chemins pré-monorepo)
# vers les nouveaux, alignés sur la structure djona_public/public/.
# À lancer UNE SEULE FOIS sur le VPS, après un `git pull` à jour.
#
# Usage : sudo bash deploy/migrate_services.sh

set -euo pipefail

PROJECT_DIR="/var/www/project/djona_public/public"
OLD_SERVICE="gunicorn_djona_public_.service"
NEW_SERVICE="gunicorn_djona_public.service"
OLD_SITE="djona_pulic"
NEW_SITE="djona.tech"

echo "==> arrêt et désactivation de l'ancien service (${OLD_SERVICE})"
systemctl stop "${OLD_SERVICE}" || true
systemctl disable "${OLD_SERVICE}" || true

echo "==> désactivation de l'ancien site nginx (${OLD_SITE})"
rm -f "/etc/nginx/sites-enabled/${OLD_SITE}"

echo "==> installation du nouveau service gunicorn (${NEW_SERVICE})"
cp "${PROJECT_DIR}/deploy/gunicorn/djona.service" "/etc/systemd/system/${NEW_SERVICE}"
systemctl daemon-reload
systemctl enable --now "${NEW_SERVICE}"

echo "==> vérification que le nouveau service tourne avant d'aller plus loin"
sleep 2
if ! systemctl is-active --quiet "${NEW_SERVICE}"; then
  echo "ERREUR : ${NEW_SERVICE} ne démarre pas. Abandon avant de toucher à nginx" >&2
  systemctl status "${NEW_SERVICE}" --no-pager || true
  exit 1
fi

echo "==> installation du nouveau site nginx (${NEW_SITE})"
cp "${PROJECT_DIR}/deploy/nginx/djona.tech.conf" "/etc/nginx/sites-available/${NEW_SITE}"
ln -sf "/etc/nginx/sites-available/${NEW_SITE}" "/etc/nginx/sites-enabled/${NEW_SITE}"

echo "==> test de la config nginx"
nginx -t

echo "==> rechargement de nginx"
systemctl reload nginx

echo "==> nettoyage des anciens fichiers"
rm -f "/etc/systemd/system/${OLD_SERVICE}"
rm -f "/etc/nginx/sites-available/${OLD_SITE}"
systemctl daemon-reload

echo
echo "==> terminé. Statut du nouveau service :"
systemctl status "${NEW_SERVICE}" --no-pager

echo
echo "==> vérification HTTP locale (gunicorn direct)"
curl -sI http://127.0.0.1:8006 | head -1 || echo "curl a échoué — vérifier manuellement"
