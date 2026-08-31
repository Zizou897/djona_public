import logging
import subprocess

import after_response
from django.conf import settings

logger = logging.getLogger(__name__)


@after_response.enable
def trigger_public_sync():
    """Relance apps.vendor_sync.sync_validated_annonces côté projet public,
    après le request_finished de la vue qui vient de valider une annonce.

    Ignoré silencieusement (juste loggé) si PUBLIC_SYNC_PYTHON /
    PUBLIC_SYNC_MANAGE_PY ne sont pas configurés — cas normal en dev local
    quand le projet public n'est pas installé sur la même machine.
    """
    python = settings.PUBLIC_SYNC_PYTHON
    manage_py = settings.PUBLIC_SYNC_MANAGE_PY
    if not python or not manage_py:
        logger.info('PUBLIC_SYNC_PYTHON/PUBLIC_SYNC_MANAGE_PY non configurés — synchro marketplace ignorée.')
        return

    try:
        result = subprocess.run(
            [python, manage_py, 'sync_validated_annonces', f'--settings={settings.PUBLIC_SYNC_SETTINGS}'],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error('sync_validated_annonces a échoué (code %s) : %s', result.returncode, result.stderr)
        else:
            logger.info('sync_validated_annonces : %s', result.stdout.strip())
    except Exception:
        logger.exception('Erreur lors du déclenchement de la synchro marketplace')
