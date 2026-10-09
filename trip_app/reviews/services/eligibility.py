"""Qui peut laisser un avis : seulement un client réellement parti (avis vérifié).

Conditions, toutes vérifiées sur la demande de voyage :
- elle appartient au client ;
- l'agence l'a confirmée (une demande annulée ou en attente ne compte pas) ;
- sa date de retour est passée : le voyage a eu lieu ;
- elle n'a pas encore d'avis (un seul avis par voyage).
"""

from django.utils import timezone

from orders.models import Order, Status


def reviewable_orders(client):
    """Demandes du client qui peuvent recevoir un avis aujourd'hui."""
    return Order.objects.filter(
        client=client,
        status=Status.CONFIRMED,
        return_date__lt=timezone.localdate(),
        review__isnull=True,
    )


def can_review(client, order: Order) -> bool:
    return reviewable_orders(client).filter(pk=order.pk).exists()
