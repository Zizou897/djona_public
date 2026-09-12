from django.conf import settings
from django.db import models


class MembreEquipe(models.Model):
    """Rattache un compte utilisateur (le « membre ») à un compte professionnel
    (le « titulaire ») pour lui donner accès au stock de ce dernier — sans que
    le membre possède ses propres annonces. Le titulaire reste seul habilité à
    ajouter/retirer des membres (voir `role_requis = 'proprietaire'` côté vues).
    """

    class Role(models.TextChoices):
        GESTIONNAIRE = 'gestionnaire', 'Gestionnaire'
        LECTURE_SEULE = 'lecture_seule', 'Lecture seule'

    compte_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membres_equipe',
    )
    membre = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rattachement_pro',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.GESTIONNAIRE)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pro_membre_equipe'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.membre} — équipe de {self.compte_pro}'


class Prospect(models.Model):
    """Carnet de contacts manuel côté vendeur professionnel : un acheteur
    intéressé que le vendeur consigne lui-même (aucune capture automatique de
    lead n'existe côté marketplace public pour l'instant — le formulaire
    véhicule public se contente de liens tel:/whatsapp directs)."""

    class Statut(models.TextChoices):
        NOUVEAU = 'nouveau', 'Nouveau'
        CONTACTE = 'contacte', 'Contacté'
        NEGOCIATION = 'negociation', 'En négociation'
        CONVERTI = 'converti', 'Converti'
        PERDU = 'perdu', 'Perdu'

    compte_pro = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prospects',
    )
    nom = models.CharField(max_length=150)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    annonce = models.ForeignKey(
        'annonces.Annonce', on_delete=models.SET_NULL, null=True, blank=True, related_name='prospects',
    )
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.NOUVEAU)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pro_prospect'
        ordering = ['-update_at']

    def __str__(self):
        return f'{self.nom} ({self.get_statut_display()})'
