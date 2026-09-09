from django.db import models


class PartnerMirror(models.Model):
    """Miroir en lecture/écriture de public.apps.core.Partner (table
    core_partner, schéma djona_public, connexion 'public_db'). Jamais migré
    depuis ce projet — le schéma réel est possédé et migré par le projet
    public. Voir apps/core/models.py côté public.

    Les logos uploadés ici doivent physiquement atterrir dans le media_cdn du
    projet public : media_cdn/partners/ de ce projet doit être un lien vers
    celui de public (voir core/settings.py, même principe que pour
    moderation.AnnoncePhotoMirror et media_cdn/annonces/).
    """

    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='partners/')
    website_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    publish = models.BooleanField(default=True)
    # NOT NULL sans défaut côté MySQL — jamais lus intentionnellement depuis ce
    # mirror, mais nécessaires pour que .create()/.save() fonctionnent (même
    # principe que AnnonceMirror.update_at).
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'core_partner'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name
