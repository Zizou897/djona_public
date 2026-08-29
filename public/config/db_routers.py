class VendorDbRouter:
    """Empêche toute migration d'être appliquée sur l'alias `vendor_db`.

    Ce schéma (djona_vendor) est entièrement possédé et migré par le projet
    vendor — ce projet ne fait que lire dedans via des modèles miroirs
    `managed=False` (apps.vendor_sync.models).
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'vendor_db':
            return False
        return None
