class VendorDbRouter:
    """Empêche toute migration d'être appliquée sur l'alias `vendor_db`.

    Ce schéma (djona_vendor, ou sa copie de test dédiée djona_vendor_test) est
    entièrement possédé et migré par le projet vendor — ce projet ne fait que
    lire/écrire dedans via des modèles miroirs `managed=False`
    (`moderation.models`). Sans ce routeur, Django tente par défaut d'appliquer
    les migrations de TOUTES les apps installées ici (y compris l'ancienne app
    locale `annonces`, qui partage le même app_label que celle du projet
    vendor mais a un historique de migrations différent) sur `vendor_db` dès
    qu'un test référence cet alias — provoquant des collisions de schéma
    (tables déjà existantes, mauvaises clés étrangères).
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'vendor_db':
            return False
        return None
