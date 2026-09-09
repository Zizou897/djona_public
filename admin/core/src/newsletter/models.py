from django.db import models


class NewsletterSubscriberMirror(models.Model):
    """Miroir en lecture/écriture de public.apps.core.NewsletterSubscriber
    (table core_newslettersubscriber, schéma djona_public, connexion
    'public_db'). Jamais migré depuis ce projet — le schéma réel est possédé
    et migré par le projet public. Les inscriptions se font uniquement via le
    formulaire public (footer) ; ce mirror ne sert qu'à consulter la liste et
    à retirer un abonné (spam, bounce...).
    """

    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'core_newslettersubscriber'
        ordering = ['-created_at']

    def __str__(self):
        return self.email
