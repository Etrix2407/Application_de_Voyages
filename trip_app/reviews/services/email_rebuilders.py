"""Reconstruction des e-mails des avis, pour les nouvelles tentatives et le renvoi manuel.

L'avis est retrouvé par la demande liée (numéro noté au journal) et son client. Le message
n'est reconstruit que s'il a toujours une raison d'être : avis encore là, client non supprimé,
avis toujours dans l'état annoncé (publié, refusé, réponse encore présente).
"""

from accounts.models import EmailKind, EmailLog
from accounts.services.email_retry import RebuiltEmail, rebuilder
from reviews.models import AgencyResponse, Review, ReviewStatus
from reviews.services.notifications import (
    PUBLISHED_TEMPLATE,
    REFUSED_TEMPLATE,
    RESPONSE_TEMPLATE,
    published_context,
    refused_context,
    response_context,
)


def _review_of(log: EmailLog, status: str) -> Review | None:
    """Avis de la demande liée, s'il appartient toujours au client du journal et a cet état."""
    if log.user is None or log.order_number is None:
        return None
    return (
        Review.objects.select_related("order__client")
        .filter(order_id=log.order_number, order__client=log.user, status=status)
        .first()
    )


@rebuilder(EmailKind.REVIEW_PUBLISHED)
def _review_published(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.PUBLISHED)
    return RebuiltEmail(PUBLISHED_TEMPLATE, published_context(review)) if review else None


@rebuilder(EmailKind.REVIEW_REFUSED)
def _review_refused(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.REFUSED)
    return RebuiltEmail(REFUSED_TEMPLATE, refused_context(review)) if review else None


@rebuilder(EmailKind.REVIEW_RESPONSE)
def _review_response(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.PUBLISHED)
    response = AgencyResponse.objects.filter(review=review).first() if review else None
    if response is None:
        return None
    # Texte actuel de la réponse ; « modifiée » si elle l'a été depuis sa création.
    created = response.updated_at == response.created_at
    return RebuiltEmail(RESPONSE_TEMPLATE, response_context(response, created))
