"""Réactions des avis aux événements des demandes de voyage."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Status, StatusChange
from reviews.services.order_events import hide_review_of_cancelled_order


@receiver(post_save, sender=StatusChange, dispatch_uid="reviews.cancelled_order")
def hide_review_when_order_cancelled(sender, instance, created, **kwargs):
    # Chaque changement d'état d'une demande est inscrit dans l'historique : on suit celui-ci.
    if created and instance.status == Status.CANCELLED:
        hide_review_of_cancelled_order(instance.order)
