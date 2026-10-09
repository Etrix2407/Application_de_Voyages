"""Modération des avis par le personnel (agents et administrateur).

| Action  | Depuis                   | Vers    | Motif       |
| ------- | ------------------------ | ------- | ----------- |
| publish | En attente de validation | Publié  | —           |
| refuse  | En attente de validation | Refusé  | obligatoire |
| hide    | Publié                   | Refusé  | obligatoire |

Le personnel ne modifie jamais le texte d'un client : il valide, refuse ou masque.
"""

from django.utils import timezone

from orders.models import Status
from reviews.models import RefusalReason, Review, ReviewStatus


class ModerationNotAllowed(Exception):
    """L'action demandée n'est pas possible dans l'état actuel de l'avis."""


def pending_reviews():
    """File de modération : du plus ancien envoi au plus récent, pour qu'aucun avis ne reste bloqué."""
    return Review.objects.filter(status=ReviewStatus.PENDING).select_related("order__client").order_by(
        "submitted_at", "pk"
    )


def publish(review: Review) -> None:
    if review.order.status != Status.CONFIRMED:
        raise ModerationNotAllowed("Le voyage a été annulé : cet avis ne peut pas être publié.")
    _move(review, ReviewStatus.PENDING, ReviewStatus.PUBLISHED, "Cet avis n'est plus en attente de validation.",
          published_at=timezone.now(), refusal_reason="", refusal_details="")


def refuse(review: Review, reason: str, details: str = "") -> None:
    _check_reason(reason, details)
    _move(review, ReviewStatus.PENDING, ReviewStatus.REFUSED, "Cet avis n'est plus en attente de validation.",
          refusal_reason=reason, refusal_details=details.strip())


def hide(review: Review, reason: str, details: str = "") -> None:
    """Retire du public un avis déjà publié (il passe « Refusé » avec son motif)."""
    _check_reason(reason, details)
    _move(review, ReviewStatus.PUBLISHED, ReviewStatus.REFUSED, "Seul un avis publié peut être masqué.",
          refusal_reason=reason, refusal_details=details.strip())


def _check_reason(reason: str, details: str) -> None:
    if reason not in RefusalReason.values or reason == RefusalReason.TRIP_CANCELLED:
        raise ValueError("Choisissez un motif dans la liste.")
    if reason == RefusalReason.OTHER and not details.strip():
        raise ValueError("Précisez le motif quand vous choisissez « Autre ».")


def _move(review: Review, expected: str, new_status: str, refusal: str, **fields) -> None:
    # Mise à jour conditionnelle : deux membres du personnel ne peuvent pas agir en même temps.
    updated = Review.objects.filter(pk=review.pk, status=expected).update(status=new_status, **fields)
    if not updated:
        raise ModerationNotAllowed(refusal)
    review.status = new_status
    for name, value in fields.items():
        setattr(review, name, value)
