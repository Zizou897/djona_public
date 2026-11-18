"""Actions métier : enregistrées à la création de la donnée (pas depuis le navigateur), donc fiables et non falsifiables.

Chaque action ne retient que des informations non personnelles (type de demande, numéro de référence,
montant) — jamais le nom, le téléphone, l'e-mail ni le contenu d'un message.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.catalog.models import Interest
from apps.core.models import ContactMessage, NewsletterSubscriber, TransportRequest
from apps.parts.models import PartOrder, PartRequest

from .tracking import track


@receiver(post_save, sender=ContactMessage, dispatch_uid='analytics_contact_message')
def on_contact_message(sender, instance, created, **kwargs):
    if created:
        track('message_contact', {'sujet': instance.subject})


@receiver(post_save, sender=TransportRequest, dispatch_uid='analytics_transport_request')
def on_transport_request(sender, instance, created, **kwargs):
    if created:
        track('demande_transport', {'reference': instance.reference})


@receiver(post_save, sender=PartRequest, dispatch_uid='analytics_part_request')
def on_part_request(sender, instance, created, **kwargs):
    if created:
        track('demande_piece', {'reference': instance.reference, 'type': instance.request_type})


@receiver(post_save, sender=PartOrder, dispatch_uid='analytics_part_order')
def on_part_order(sender, instance, created, **kwargs):
    if created:
        track('commande_piece', {'reference': instance.reference})


@receiver(post_save, sender=NewsletterSubscriber, dispatch_uid='analytics_newsletter')
def on_newsletter_subscriber(sender, instance, created, **kwargs):
    if created:
        track('inscription_newsletter')


@receiver(post_save, sender=Interest, dispatch_uid='analytics_vehicle_interest')
def on_vehicle_interest(sender, instance, created, **kwargs):
    if created:
        rental = bool(instance.rental_start)
        track('demande_location' if rental else 'interet_vehicule', {'vehicule': instance.vehicle_id})
