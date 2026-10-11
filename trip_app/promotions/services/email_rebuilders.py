"""Construction des e-mails promotionnels, au premier envoi comme aux nouvelles tentatives.

Les e-mails promotionnels sont mis en attente (mailing.py) : le premier envoi passe lui aussi par
cette fonction. Rien n'est envoyé si le message n'a plus de raison d'être : client supprimé,
adresse changée depuis, client qui n'accepte plus les promotions (désinscrit, compte désactivé...),
envoi ou promotion supprimés, promotion désactivée ou terminée entre-temps.
"""

from accounts.models import EmailKind, EmailLog, User
from accounts.services.email_retry import RebuiltEmail, rebuilder
from accounts.services.unsubscribe import unsubscribe_headers
from promotions.models import PromotionMailing
from promotions.services.mailing import can_be_mailed, promotion_email_context


@rebuilder(EmailKind.PROMOTION)
def _promotion(log: EmailLog) -> RebuiltEmail | None:
    user = log.user
    if user is None or user.email != log.recipient or log.promotion_mailing_number is None:
        return None
    if not User.objects.promotion_recipients().filter(pk=user.pk).exists():
        return None
    mailing = PromotionMailing.objects.select_related("promotion").filter(pk=log.promotion_mailing_number).first()
    if mailing is None or not can_be_mailed(mailing.promotion):
        return None
    return RebuiltEmail(promotion_email_context(mailing, user), unsubscribe_headers(user))
