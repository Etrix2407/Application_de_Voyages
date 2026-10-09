"""Le client écrit, modifie ou supprime son avis.

Tout avis écrit ou modifié repasse « En attente de validation » : il n'est visible
du public qu'après la validation d'un membre du personnel. Le client garde la main
pendant 30 jours après la création (modèle : EDIT_PERIOD).
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from orders.models import Status
from reviews.models import Review, ReviewStatus
from reviews.services.eligibility import can_review


class ReviewNotAllowed(Exception):
    """Ce voyage ne peut pas (ou plus) recevoir d'avis de ce client."""


class ReviewLocked(Exception):
    """L'avis ne peut plus être modifié ni supprimé."""


def client_can_edit(review: Review) -> bool:
    # Un voyage annulé après coup ne se « répare » pas en modifiant l'avis.
    return review.can_be_changed_by_client() and review.order.status == Status.CONFIRMED


def client_can_delete(review: Review) -> bool:
    return review.can_be_changed_by_client()


def write_review(client, review: Review) -> Review:
    """Enregistre un nouvel avis (validé par le formulaire) sur une demande de ce client."""
    if not can_review(client, review.order):
        raise ReviewNotAllowed
    review.status = ReviewStatus.PENDING
    review.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            review.save()
    except IntegrityError:
        # Deux envois simultanés : la base garde un seul avis par demande.
        raise ReviewNotAllowed from None
    return review


def update_review(review: Review) -> Review:
    """Enregistre la modification (déjà appliquée par le formulaire) et la renvoie en modération.

    Un avis publié est masqué au public en attendant ; le motif d'un refus est effacé.
    """
    if not client_can_edit(review):
        raise ReviewLocked
    review.status = ReviewStatus.PENDING
    review.submitted_at = timezone.now()
    review.refusal_reason = ""
    review.refusal_details = ""
    review.full_clean(validate_unique=False)
    review.save()
    return review


def delete_review(review: Review) -> None:
    if not client_can_delete(review):
        raise ReviewLocked
    review.delete()
