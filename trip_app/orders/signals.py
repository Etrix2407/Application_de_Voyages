"""Réactions des demandes de voyage aux événements des autres applications."""

from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from accounts.signals import email_changed
from orders.services.privacy import anonymize_orders_of
from orders.services.promotions import refresh_client_fingerprint


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def anonymize_orders_of_deleted_client(sender, instance, **kwargs):
    # Quel que soit le chemin de suppression (profil, purge, base), dans la même transaction.
    anonymize_orders_of(instance)


@receiver(email_changed)
def follow_new_email_address(sender, user, **kwargs):
    # La limite d'utilisation des promotions par client suit le client sur sa nouvelle adresse.
    refresh_client_fingerprint(user)
