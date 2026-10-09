"""Modération des avis par le personnel (agents et administrateur).

| Action  | Depuis                   | Vers    | Motif       |
| ------- | ------------------------ | ------- | ----------- |
| publish | En attente de validation | Publié  | —           |
| refuse  | En attente de validation | Refusé  | obligatoire |
| hide    | Publié                   | Refusé  | obligatoire |

Le personnel ne modifie jamais le texte d'un client : il valide, refuse ou masque.
Chaque action porte sur la version relue (`seen_version`, numéro de version de l'avis) :
si le client a modifié son avis entre-temps, l'action est refusée.
"""

from django.utils import timezone

from orders.models import Status
from reviews.models import STAFF_REFUSAL_REASONS, Review, ReviewStatus, refusal_problem


class ModerationNotAllowed(Exception):
    """L'action demandée n'est pas possible dans l'état actuel de l'avis."""


def pending_reviews():
    """File de modération : du plus ancien envoi au plus récent, pour qu'aucun avis ne reste bloqué."""
    return Review.objects.filter(status=ReviewStatus.PENDING).select_related("order__client").order_by(
        "submitted_at", "pk"
    )


def publish(review: Review, seen_version=None) -> None:
    if review.order.status != Status.CONFIRMED:
        raise ModerationNotAllowed("Le voyage a été annulé : cet avis ne peut pas être publié.")
    _move(review, ReviewStatus.PENDING, ReviewStatus.PUBLISHED, "Cet avis n'est plus en attente de validation.",
          seen_version, published_at=timezone.now(), refusal_reason="", refusal_details="")


def refuse(review: Review, reason: str, details: str = "", seen_version=None) -> None:
    _check_reason(reason, details)
    _move(review, ReviewStatus.PENDING, ReviewStatus.REFUSED, "Cet avis n'est plus en attente de validation.",
          seen_version, refusal_reason=reason, refusal_details=details.strip())


def hide(review: Review, reason: str, details: str = "", seen_version=None) -> None:
    """Retire du public un avis déjà publié (il passe « Refusé » avec son motif)."""
    _check_reason(reason, details)
    _move(review, ReviewStatus.PUBLISHED, ReviewStatus.REFUSED, "Seul un avis publié peut être masqué.",
          seen_version, refusal_reason=reason, refusal_details=details.strip())


def _check_reason(reason: str, details: str) -> None:
    if reason not in STAFF_REFUSAL_REASONS:
        raise ValueError("Choisissez un motif dans la liste.")
    problem = refusal_problem(reason, details)
    if problem:
        raise ValueError(next(iter(problem.values())))


CHANGED_MESSAGE = "Le client a modifié cet avis pendant votre lecture : relisez-le avant de décider."


def _move(review: Review, expected: str, new_status: str, refusal: str, seen_version, **fields) -> None:
    # Mise à jour conditionnelle : deux membres du personnel ne peuvent pas agir en même temps,
    # et l'action ne s'applique qu'à la version relue.
    matching = Review.objects.filter(pk=review.pk, status=expected)
    if seen_version is not None:
        if not matching.filter(version=seen_version).exists() and matching.exists():
            raise ModerationNotAllowed(CHANGED_MESSAGE)
        matching = matching.filter(version=seen_version)
    updated = matching.update(status=new_status, **fields)
    if not updated:
        raise ModerationNotAllowed(refusal)
    review.status = new_status
    for name, value in fields.items():
        setattr(review, name, value)
