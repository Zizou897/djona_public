from django.db import models


class Partner(models.Model):
    """Partenaire affiché dans le bandeau « Ils nous font confiance », géré
    depuis le back-office (admin.moderation... voir admin/core/src/partners/).
    Jamais créé/modifié par une action publique — lecture seule côté public.
    """

    name = models.CharField('nom', max_length=100)
    logo = models.ImageField('logo', upload_to='partners/')
    website_url = models.URLField('site web', blank=True)
    order = models.PositiveIntegerField('ordre', default=0)
    publish = models.BooleanField('actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'partenaire'
        verbose_name_plural = 'partenaires'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class NewsletterSubscriber(models.Model):
    """Inscrit à la newsletter — formulaire dans le footer public. Consultable
    en lecture seule depuis le back-office (voir admin/core/src/partners/, ou
    l'app dédiée si le back-office ajoute la sienne).
    """

    email = models.EmailField('email', unique=True)
    is_active = models.BooleanField('actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'abonné newsletter'
        verbose_name_plural = 'abonnés newsletter'
        ordering = ['-created_at']

    def __str__(self):
        return self.email
