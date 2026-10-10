"""E-mails envoyés au client sur son avis (v5) : publié, refusé ou retiré, réponse de l'agence.

Le client dont le compte est supprimé (avis anonymisé) ne reçoit rien.
"""

from django.urls import reverse

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from reviews.models import AgencyResponse, RefusalReason, Review
from reviews.services.writing import client_can_edit


def notify_published(review: Review) -> None:
    """« Merci, votre avis est en ligne », avec le lien vers la destination si elle est visible."""
    destination_link = ""
    if Review.objects.public().filter(pk=review.pk).exists():
        destination_link = site_url(reverse("destination_detail", args=[review.order.destination_id]))
    _notify(review, EmailKind.REVIEW_PUBLISHED, "reviews/emails/review_published.txt",
            {"destination_link": destination_link})


def notify_refused(review: Review) -> None:
    """Avis refusé, masqué ou retiré (voyage annulé) : le motif, et la date limite de correction.

    Le rappel de correction n'apparaît que si le client peut encore modifier son avis
    (30 jours après sa création, voyage toujours confirmé : voir client_can_edit).
    Délai dépassé : l'e-mail le dit, sauf pour « Voyage annulé » (correction impossible pour une autre raison).
    """
    deadline_passed = (
        not review.can_be_changed_by_client() and review.refusal_reason != RefusalReason.TRIP_CANCELLED
    )
    _notify(review, EmailKind.REVIEW_REFUSED, "reviews/emails/review_refused.txt",
            {"can_correct": client_can_edit(review), "deadline_passed": deadline_passed})


def notify_response(response: AgencyResponse, created: bool) -> None:
    """Réponse de l'agence publiée (`created`) ou modifiée sous l'avis du client."""
    _notify(response.review, EmailKind.REVIEW_RESPONSE, "reviews/emails/review_response.txt",
            {"response": response, "created": created})


def _notify(review: Review, kind: EmailKind, template_name: str, extra: dict) -> None:
    client = review.order.client
    if client is None:
        return
    context = {
        "client": client,
        "review": review,
        "my_reviews_link": site_url(reverse("my_reviews")),
        **extra,
    }
    send_email(client.email, kind, template_name, context, user=client, order_number=review.order_id)
