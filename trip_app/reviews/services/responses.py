"""Réponse de l'agence à un avis (décisions validées) :

- une seule réponse par avis, seulement sur un avis **publié** ;
- écrite par un agent ou l'administrateur, signée de son **prénom** ;
- seul son auteur la modifie (un administrateur si l'auteur a quitté l'agence :
  compte supprimé ou désactivé) ;
- supprimée si le client modifie son avis (voir services/writing.py).
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from reviews.models import AgencyResponse, Review, ReviewStatus
from reviews.services.notifications import notify_response


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
    if response.author is None or not response.author.is_active:
        return staff_member.is_administrator
    return response.author_id == staff_member.pk


CHANGED_MESSAGE = "Le client a modifié cet avis pendant votre lecture : relisez-le avant de répondre."


def save_response(review: Review, staff_member, text: str, seen_version: int | None = None) -> AgencyResponse:
    """Crée la réponse, ou modifie celle de son auteur.

    `seen_version` : version de l'avis lue par l'agent (champ caché du formulaire). Si le client a
    modifié son avis depuis, même republié entre-temps, la réponse est refusée : elle porterait sur
    un texte que l'agent n'a pas lu. Sans `seen_version`, la version de `review` sert de référence.
    """
    if not can_write_response(review, staff_member):
        raise ResponseNotAllowed
    response = existing_response(review) or AgencyResponse(
        review=review, author=staff_member, author_first_name=staff_member.first_name
    )
    created = response.pk is None
    response.text = text.strip()
    response.updated_at = timezone.now()
    if created:
        # Même instant à la création : une réponse jamais modifiée se reconnaît (nouvelles tentatives d'envoi).
        response.created_at = response.updated_at
    response.full_clean(exclude=["review"])
    version = review.version if seen_version is None else seen_version
    try:
        with transaction.atomic():
            # Revérifié dans la transaction, qui détient déjà le verrou d'écriture (réglage « IMMEDIATE »
            # de settings.py) : si le client a modifié son avis entre-temps, la version a changé et
            # sa modification a supprimé la réponse ; elle ne doit pas être recréée sous le nouveau texte.
            if not Review.objects.filter(pk=review.pk, status=ReviewStatus.PUBLISHED, version=version).exists():
                raise ResponseNotAllowed(CHANGED_MESSAGE)
            response.save()
    except IntegrityError:
        # Deux agents ont répondu au même instant : la base garde une seule réponse par avis.
        raise ResponseNotAllowed from None
    # Le client est prévenu à la création comme à chaque modification de la réponse.
    notify_response(response, created)
    return response
