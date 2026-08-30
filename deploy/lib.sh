# Fonctions partagées par les scripts deploy_*.sh — à sourcer, pas à exécuter.

# health_check <url> <code_ok_1> [code_ok_2 ...]
# Échoue (return 1) si le code HTTP obtenu n'est dans aucun des codes attendus.
health_check() {
  local url="$1"; shift
  local ok_codes=("$@")
  local status
  status="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 15 "$url" || echo "000")"

  for code in "${ok_codes[@]}"; do
    if [ "$status" = "$code" ]; then
      echo "    ${url} -> ${status} OK"
      return 0
    fi
  done

  echo "ERREUR : ${url} a répondu ${status} (attendu : ${ok_codes[*]})" >&2
  return 1
}

# restart_and_check <service> <url> [code_ok_1 ...]
# Redémarre le service, vérifie qu'il tourne, puis vérifie la vraie réponse HTTP.
# N'écrase jamais un service qui fonctionnait si la nouvelle version casse tout —
# le service reste redémarré (dernier code en date), mais le script sort en erreur
# clairement plutôt que de prétendre que le déploiement a réussi.
restart_and_check() {
  local service="$1" url="$2"; shift 2
  local ok_codes=("$@")

  echo "==> redémarrage de ${service}"
  systemctl restart "$service"
  sleep 2

  if ! systemctl is-active --quiet "$service"; then
    echo "ERREUR : ${service} n'a pas démarré." >&2
    systemctl status "$service" --no-pager || true
    journalctl -u "$service" --no-pager -n 20 || true
    return 1
  fi

  echo "==> vérification HTTP réelle"
  health_check "$url" "${ok_codes[@]}"
}
