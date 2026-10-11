"""Reconstruction des e-mails des avis, pour les nouvelles tentatives et le renvoi manuel.

L'avis est retrouvé par la demande liée (numéro noté au journal) et son client. Le message
n'est reconstruit que s'il a toujours une raison d'être : avis encore là, client non supprimé
et toujours à la même adresse, avis toujours dans l'état annoncé (publié, refusé, réponse encore présente).
"""

from accounts.models import EmailLog
from accounts.services.email_rebuilders import account_at_recipient
from accounts.services.email_retry import RebuiltEmail, rebuilder
from reviews.models import AgencyResponse, Review, ReviewEmail, ReviewStatus
from reviews.services.eligibility import reviewable_orders
from reviews.services.invitations import review_invitation_context
from reviews.services.notifications import published_context, refused_context, response_context


def _review_of(log: EmailLog, status: str) -> Review | None:
    """Avis de la demande liée, s'il appartient toujours au client du journal (même adresse) et a cet état."""
    client = account_at_recipient(log)
    if client is None or log.order_number is None:
        return None
    return (
        Review.objects.select_related("order__client")
        .filter(order_id=log.order_number, order__client=client, status=status)
        .first()
    )


@rebuilder(ReviewEmail.REVIEW_PUBLISHED)
def _review_published(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.PUBLISHED)
    return RebuiltEmail(published_context(review)) if review else None


@rebuilder(ReviewEmail.REVIEW_REFUSED)
def _review_refused(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.REFUSED)
    return RebuiltEmail(refused_context(review)) if review else None


@rebuilder(ReviewEmail.REVIEW_RESPONSE)
def _review_response(log: EmailLog) -> RebuiltEmail | None:
    review = _review_of(log, ReviewStatus.PUBLISHED)
    response = AgencyResponse.objects.filter(review=review).first() if review else None
    if response is None:
        return None
    # Texte actuel de la réponse ; « modifiée » si elle l'a été depuis sa création.
    created = response.updated_at == response.created_at
    return RebuiltEmail(response_context(response, created))


@rebuilder(ReviewEmail.REVIEW_INVITATION)
def _review_invitation(log: EmailLog) -> RebuiltEmail | None:
    # Seulement si le voyage peut encore recevoir un avis (ni avis laissé, ni annulation depuis).
    client = account_at_recipient(log)
    if client is None or log.order_number is None:
        return None
    order = reviewable_orders(client).filter(pk=log.order_number).select_related("client").first()
    return RebuiltEmail(review_invitation_context(order)) if order else None
