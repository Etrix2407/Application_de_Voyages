"""Réactions des avis aux événements des autres applications."""

from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from orders.models import Status, StatusChange
from reviews.services.order_events import hide_review_of_cancelled_order
from reviews.services.privacy import erase_signatures_of


@receiver(post_save, sender=StatusChange, dispatch_uid="reviews.cancelled_order")
def hide_review_when_order_cancelled(sender, instance, created, **kwargs):
    # Chaque changement d'état d'une demande est inscrit dans l'historique : on suit celui-ci.
    if created and instance.status == Status.CANCELLED:
        hide_review_of_cancelled_order(instance.order)


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL, dispatch_uid="reviews.deleted_client")
def erase_signatures_of_deleted_client(sender, instance, **kwargs):
    # Avant la suppression : les demandes sont encore liées au client. Même transaction.
    erase_signatures_of(instance)
