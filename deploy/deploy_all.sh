#!/usr/bin/env bash
# Déploiement des 3 projets (public, admin, vendor) en une commande.
# À lancer sur le VPS après chaque modification poussée sur main.
#
# Usage : sudo bash deploy/deploy_all.sh
#
# Chaque projet est vérifié (manage.py check --deploy) et testé en HTTP réel
# APRÈS son propre redémarrage, avant de passer au suivant. Un projet qui
# échoue n'empêche pas les autres d'être déployés — le script continue et
# donne un résumé clair à la fin, avec un code de sortie non nul si au moins
# un projet a échoué.

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> git pull (${REPO_ROOT})"
if ! git -C "$REPO_ROOT" pull; then
  echo "ERREUR : git pull a échoué, abandon avant de toucher aux services." >&2
  exit 1
fi

declare -A RESULTS
for project in public admin vendor; do
  echo
  echo "########## ${project} ##########"
  if bash "${SCRIPT_DIR}/deploy_${project}.sh"; then
    RESULTS[$project]="OK"
  else
    RESULTS[$project]="ÉCHEC"
  fi
done

echo
echo "==================== résumé ===================="
overall=0
for project in public admin vendor; do
  status="${RESULTS[$project]}"
  echo "  ${project} : ${status}"
  [ "$status" = "ÉCHEC" ] && overall=1
done
echo "=================================================="

if [ "$overall" -ne 0 ]; then
  echo "Au moins un projet a échoué — vérifie les logs ci-dessus avant de considérer le déploiement terminé." >&2
fi

exit "$overall"
