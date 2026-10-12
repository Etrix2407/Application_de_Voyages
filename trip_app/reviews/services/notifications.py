"""E-mails envoyés au client sur son avis (v5) : publié, refusé ou retiré, réponse de l'agence.

Le client dont le compte est supprimé (avis anonymisé) ne reçoit rien.
Les fonctions *_context donnent la valeur des champs variables de chaque e-mail (voir
reviews/services/email_texts.py) ; elles servent aussi à reconstruire un message pour une
nouvelle tentative (voir reviews/services/email_rebuilders.py).
"""

from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.services.emails import send_email, site_url
from common.text import duration_text
from reviews.models import EDIT_PERIOD, AgencyResponse, RefusalReason, Review, ReviewEmail
from reviews.services.writing import client_can_edit


def notify_published(review: Review) -> None:
    _notify(review, ReviewEmail.REVIEW_PUBLISHED, published_context)


def notify_refused(review: Review) -> None:
    _notify(review, ReviewEmail.REVIEW_REFUSED, refused_context)


def notify_response(response: AgencyResponse, created: bool) -> None:
    """Réponse de l'agence publiée (`created`) ou modifiée sous l'avis du client."""
    _notify(response.review, ReviewEmail.REVIEW_RESPONSE, lambda review: response_context(response, created))


def published_context(review: Review) -> dict:
    """« Merci, votre avis est en ligne », avec le lien vers la destination si elle est visible."""
    destination_link = ""
    if Review.objects.public().filter(pk=review.pk).exists():
        link = site_url(reverse("destination_detail", args=[review.order.destination_id]))
        destination_link = f"Vous pouvez le lire sur la page de la destination :\n\n{link}"
    return {**_base_context(review), "lien vers la destination": destination_link}


def refused_context(review: Review) -> dict:
    """Avis refusé, masqué ou retiré (voyage annulé) : le motif, et la date limite de correction.

    Le rappel de correction n'apparaît que si le client peut encore modifier son avis
    (30 jours après sa création, voyage toujours confirmé : voir client_can_edit).
    Délai dépassé : l'e-mail le dit, sauf pour « Voyage annulé » (correction impossible pour une autre raison).
    """
    correction = ""
    if client_can_edit(review):
        # Date à l'heure belge : en UTC, une fin de délai en fin de soirée tomberait la veille.
        deadline = date_format(timezone.localtime(review.editable_until), "j F Y")
        correction = (
            f"Vous pouvez corriger votre avis jusqu'au {deadline}, depuis la "
            "page « Mes avis ». Il sera de nouveau relu par l'agence avant sa publication.\n\n"
            f"{site_url(reverse('my_reviews'))}"
        )
    elif not review.can_be_changed_by_client() and review.refusal_reason != RefusalReason.TRIP_CANCELLED:
        correction = f"Le délai de {duration_text(EDIT_PERIOD)} pour corriger cet avis est dépassé."
    return {**_base_context(review), "motif": review.refusal_label, "correction": correction}


def response_context(response: AgencyResponse, created: bool) -> dict:
    return {
        **_base_context(response.review),
        "annonce": "L'agence a répondu" if created else "L'agence a modifié sa réponse",
        "auteur": response.author_first_name,
        "réponse": response.text,
        "lien": site_url(reverse("my_reviews")),
    }


def _base_context(review: Review) -> dict:
    order = review.order
    return {
        "prénom": order.client.first_name,
        "titre": review.title,
        "destination": order.destination_label,
    }


def _notify(review: Review, kind: ReviewEmail, build_context) -> None:
    client = review.order.client
    if client is None:
        return
    send_email(client.email, kind, build_context(review), user=client, order_number=review.order_id)
