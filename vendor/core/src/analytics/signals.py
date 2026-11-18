"""Actions métier de l'espace vendeur, enregistrées à la création de la donnée (fiables, non falsifiables).

Aucune donnée personnelle : ni nom, ni e-mail, ni téléphone — seulement le type de compte ou l'identifiant d'annonce.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from annonces.models import Annonce
from app.models import DemandePassagePro, Utilisateur

from .tracking import track


@receiver(post_save, sender=Utilisateur, dispatch_uid='analytics_vendor_signup')
def on_vendor_signup(sender, instance, created, **kwargs):
    if created:
        track('inscription_vendeur', {'type_compte': instance.type_compte})


@receiver(post_save, sender=Annonce, dispatch_uid='analytics_listing_created')
def on_listing_created(sender, instance, created, **kwargs):
    if created:
        track('annonce_creee', {'annonce': instance.pk})


@receiver(post_save, sender=DemandePassagePro, dispatch_uid='analytics_pro_request')
def on_pro_request(sender, instance, created, **kwargs):
    if created:
        track('demande_pro')
