class VendorDbRouter:
    """Empêche toute migration d'être appliquée sur les alias `vendor_db` et
    `public_db`.

    Ces schémas (djona_vendor / djona_vendor_test, et djona_public) sont
    entièrement possédés et migrés par leurs projets respectifs — ce projet ne
    fait que lire/écrire dedans via des modèles miroirs `managed=False`
    (`moderation.models`). Sans ce routeur, Django tente par défaut d'appliquer
    les migrations de TOUTES les apps installées ici (y compris l'ancienne app
    locale `annonces`, qui partage le même app_label que celle du projet
    vendor mais a un historique de migrations différent) sur ces alias dès
    qu'un test les référence — provoquant des collisions de schéma (tables
    déjà existantes, mauvaises clés étrangères).
    """

    EXTERNAL_ALIASES = {'vendor_db', 'public_db'}

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db in self.EXTERNAL_ALIASES:
            return False
        return None
