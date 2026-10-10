"""Invitation à donner un avis, envoyée le lendemain du retour (v5).

Envoyée chaque jour par la commande planifiée send_trip_reminders, pour chaque voyage qui
peut recevoir un avis (règles de eligibility.py) : rattrapage tant que l'avis reste possible,
jamais si le client a déjà donné son avis. La date d'envoi, notée sur la demande, empêche
tout doublon.
"""

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from orders.models import Order
from reviews.services.eligibility import all_reviewable_orders

TEMPLATE = "reviews/emails/review_invitation.txt"


def due_review_invitations():
    """Voyages qui peuvent recevoir un avis et dont l'invitation n'est pas encore partie."""
    return all_reviewable_orders().filter(review_invitation_sent_at__isnull=True)


def send_review_invitations() -> int:
    """Envoie les invitations dues ; renvoie le nombre d'invitations envoyées."""
    return sum(_send_invitation(order) for order in due_review_invitations().select_related("client"))


def review_invitation_context(order: Order) -> dict:
    return {
        "order": order,
        "user": order.client,
        "review_link": site_url(reverse("create_review", kwargs={"order_pk": order.pk})),
    }


@transaction.atomic
def _send_invitation(order: Order) -> bool:
    # Marque d'abord la demande, sous condition : deux envois simultanés ne partent pas tous les deux.
    claimed = Order.objects.filter(pk=order.pk, review_invitation_sent_at__isnull=True).update(
        review_invitation_sent_at=timezone.now()
    )
    if not claimed:
        return False
    send_email(
        order.client.email,
        EmailKind.REVIEW_INVITATION,
        TEMPLATE,
        review_invitation_context(order),
        user=order.client,
        order_number=order.pk,
    )
    return True
