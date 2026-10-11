"""Envoi d'une promotion par e-mail aux clients consentants (v5), décidé par l'administrateur.

L'envoi est seulement programmé : un e-mail par client est mis en attente dans le journal, puis
la commande planifiée process_emails les envoie à son prochain passage (5 minutes au plus).
Le message est construit à ce moment-là (email_rebuilders.py) : un client qui se désinscrit
entre-temps ne reçoit rien.
"""

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind, User
from accounts.services.emails import queue_emails, site_url
from accounts.services.unsubscribe import unsubscribe_link
from promotions.models import Promotion, PromotionMailing, State

TEMPLATE = "promotions/emails/promotion.txt"


class NoRecipients(Exception):
    """Aucun client ne peut recevoir l'envoi (consentement, adresse confirmée, compte actif)."""


def can_be_mailed(promotion: Promotion) -> bool:
    """Seules les promotions en cours ou à venir peuvent être envoyées."""
    return promotion.state() in (State.RUNNING, State.UPCOMING)


@transaction.atomic
def send_promotion_mailing(promotion: Promotion, message: str, author: User) -> PromotionMailing:
    """Programme l'envoi à tous les clients consentants ; lève NoRecipients s'il n'y en a aucun."""
    recipients = list(User.objects.promotion_recipients().only("pk", "email"))
    if not recipients:
        raise NoRecipients
    mailing = PromotionMailing.objects.create(
        promotion=promotion,
        message=message,
        author=author,
        author_name=author.get_full_name(),
        recipients_count=len(recipients),
    )
    queue_emails(recipients, EmailKind.PROMOTION, promotion_mailing_number=mailing.pk)
    return mailing


def promotion_email_context(mailing: PromotionMailing, user: User) -> dict:
    """Variables de l'e-mail d'un client, lues au moment de l'envoi."""
    promotion = mailing.promotion
    # La page « Nos offres du moment » ne montre que les promotions automatiques en cours.
    on_offers_page = promotion.is_automatic and promotion.state() == State.RUNNING
    return {
        "first_name": user.first_name,
        "message": mailing.message,
        "promotion": promotion,
        "upcoming": promotion.starts_on > timezone.localdate(),
        "link": site_url(reverse("offers" if on_offers_page else "country_list")),
        "unsubscribe_link": unsubscribe_link(user),
    }
