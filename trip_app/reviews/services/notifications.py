"""E-mails envoyés au client sur son avis (v5) : publié, refusé ou retiré, réponse de l'agence.

Le client dont le compte est supprimé (avis anonymisé) ne reçoit rien.
Les fonctions *_context servent aussi à reconstruire un message pour une nouvelle tentative
(voir reviews/services/email_rebuilders.py).
"""

from django.urls import reverse

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from reviews.models import AgencyResponse, RefusalReason, Review
from reviews.services.writing import client_can_edit

PUBLISHED_TEMPLATE = "reviews/emails/review_published.txt"
REFUSED_TEMPLATE = "reviews/emails/review_refused.txt"
RESPONSE_TEMPLATE = "reviews/emails/review_response.txt"


def notify_published(review: Review) -> None:
    _notify(review, EmailKind.REVIEW_PUBLISHED, PUBLISHED_TEMPLATE, published_context)


def notify_refused(review: Review) -> None:
    _notify(review, EmailKind.REVIEW_REFUSED, REFUSED_TEMPLATE, refused_context)


def notify_response(response: AgencyResponse, created: bool) -> None:
    """Réponse de l'agence publiée (`created`) ou modifiée sous l'avis du client."""
    _notify(response.review, EmailKind.REVIEW_RESPONSE, RESPONSE_TEMPLATE,
            lambda review: response_context(response, created))


def published_context(review: Review) -> dict:
    """« Merci, votre avis est en ligne », avec le lien vers la destination si elle est visible."""
    destination_link = ""
    if Review.objects.public().filter(pk=review.pk).exists():
        destination_link = site_url(reverse("destination_detail", args=[review.order.destination_id]))
    return {**_base_context(review), "destination_link": destination_link}


def refused_context(review: Review) -> dict:
    """Avis refusé, masqué ou retiré (voyage annulé) : le motif, et la date limite de correction.

    Le rappel de correction n'apparaît que si le client peut encore modifier son avis
    (30 jours après sa création, voyage toujours confirmé : voir client_can_edit).
    Délai dépassé : l'e-mail le dit, sauf pour « Voyage annulé » (correction impossible pour une autre raison).
    """
    deadline_passed = (
        not review.can_be_changed_by_client() and review.refusal_reason != RefusalReason.TRIP_CANCELLED
    )
    return {**_base_context(review), "can_correct": client_can_edit(review), "deadline_passed": deadline_passed}


def response_context(response: AgencyResponse, created: bool) -> dict:
    return {**_base_context(response.review), "response": response, "created": created}


def _base_context(review: Review) -> dict:
    return {"client": review.order.client, "review": review, "my_reviews_link": site_url(reverse("my_reviews"))}


def _notify(review: Review, kind: EmailKind, template_name: str, build_context) -> None:
    client = review.order.client
    if client is None:
        return
    send_email(client.email, kind, template_name, build_context(review), user=client, order_number=review.order_id)
