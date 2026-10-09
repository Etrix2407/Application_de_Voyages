"""Réponse de l'agence à un avis (décisions validées) :

- une seule réponse par avis, seulement sur un avis **publié** ;
- écrite par un agent ou l'administrateur, signée de son **prénom** ;
- seul son auteur la modifie (un administrateur si l'auteur n'existe plus) ;
- supprimée si le client modifie son avis (voir services/writing.py).
"""

from django.utils import timezone

from reviews.models import AgencyResponse, Review, ReviewStatus


class ResponseNotAllowed(Exception):
    """La réponse ne peut pas être écrite ou modifiée par cette personne, ou pas sur cet avis."""


def existing_response(review: Review) -> AgencyResponse | None:
    return AgencyResponse.objects.filter(review=review).first()


def can_write_response(review: Review, staff_member) -> bool:
    if review.status != ReviewStatus.PUBLISHED or not staff_member.is_staff_member:
        return False
    response = existing_response(review)
    if response is None:
        return True
    if response.author_id is None:
        return staff_member.is_administrator
    return response.author_id == staff_member.pk


def save_response(review: Review, staff_member, text: str) -> AgencyResponse:
    """Crée la réponse, ou modifie celle de son auteur."""
    if not can_write_response(review, staff_member):
        raise ResponseNotAllowed
    response = existing_response(review) or AgencyResponse(
        review=review, author=staff_member, author_first_name=staff_member.first_name
    )
    response.text = text.strip()
    response.updated_at = timezone.now()
    response.full_clean(exclude=["review"])
    response.save()
    return response
