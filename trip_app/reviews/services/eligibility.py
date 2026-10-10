"""Qui peut laisser un avis : seulement un client réellement parti (avis vérifié).

Conditions, toutes vérifiées sur la demande de voyage :
- elle appartient au client ;
- l'agence l'a confirmée (une demande annulée ou en attente ne compte pas) ;
- sa date de retour est passée : le voyage a eu lieu ;
- elle n'a pas encore d'avis (un seul avis par voyage), et aucun avis n'y a été retiré.
"""

from django.utils import timezone

from orders.models import Order, Status


def all_reviewable_orders():
    """Demandes qui peuvent recevoir un avis aujourd'hui, tous clients confondus (client supprimé exclu)."""
    return Order.objects.filter(
        client__isnull=False,
        status=Status.CONFIRMED,
        return_date__lt=timezone.localdate(),
        review__isnull=True,
        review_withdrawal__isnull=True,
    )


def reviewable_orders(client):
    """Demandes du client qui peuvent recevoir un avis aujourd'hui."""
    return all_reviewable_orders().filter(client=client)


def can_review(client, order: Order) -> bool:
    return reviewable_orders(client).filter(pk=order.pk).exists()
