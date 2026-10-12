"""Construction des e-mails promotionnels, au premier envoi comme aux nouvelles tentatives.

Les e-mails promotionnels sont mis en attente (mailing.py) : le premier envoi passe lui aussi par
cette fonction. Rien n'est envoyé si le message n'a plus de raison d'être : client supprimé,
adresse changée depuis, client qui n'accepte plus les promotions (désinscrit, compte désactivé...),
envoi ou promotion supprimés, promotion désactivée ou terminée entre-temps, ou qui ne vise plus
aucun pays ni aucune destination proposé. Les pays et destinations désactivés ne sont pas cités.

Deux requêtes au plus par message : l'envoi avec sa promotion (et le consentement du client),
puis les pays ou destinations visés.
"""

from django.db.models import Exists

from accounts.models import EmailLog, User
from accounts.services.email_retry import RebuiltEmail, rebuilder
from accounts.services.unsubscribe import unsubscribe_headers
from promotions.models import PromotionEmail, PromotionMailing
from promotions.services.mailing import can_be_mailed, promotion_email_context


# Envoi en nombre (queue_emails) : premier envoi au passage suivant de process_emails, après les autres e-mails.
@rebuilder(PromotionEmail.PROMOTION, queued=True)
def _promotion(log: EmailLog) -> RebuiltEmail | None:
    user = log.user
    if user is None or user.email != log.recipient or log.promotion_mailing_number is None:
        return None
    mailing = (
        PromotionMailing.objects.select_related("promotion")
        .annotate(still_accepted=Exists(User.objects.promotion_recipients().filter(pk=user.pk)))
        .filter(pk=log.promotion_mailing_number)
        .first()
    )
    if mailing is None or not mailing.still_accepted:
        return None
    promotion = mailing.promotion
    if not can_be_mailed(promotion):
        return None
    return RebuiltEmail(promotion_email_context(mailing, user), unsubscribe_headers(user))
