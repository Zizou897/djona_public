from django.db import models


class Convention(models.Model):
    """Base abstraite pour les modèles publiables (cf. AGENTS.md §5)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    publish = models.BooleanField(default=False)

    class Meta:
        abstract = True


# TODO (AGENTS.md §5) : Vehicle, VehicleImage, Favorite — à implémenter avec
# l'écran Listing/Recherche (/vehicules/).
