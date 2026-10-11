"""Envoi d'une promotion par e-mail aux clients consentants (v5), décidé par l'administrateur.

L'envoi est seulement programmé : un e-mail par client est mis en attente dans le journal, puis
la commande planifiée process_emails les envoie à son prochain passage (5 minutes au plus).
Le message est construit à ce moment-là (email_rebuilders.py) : un client qui se désinscrit
entre-temps ne reçoit rien.
"""

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import EmailKind, User
from accounts.services.emails import queue_emails, site_url
from accounts.services.unsubscribe import unsubscribe_link
from promotions.models import Promotion, PromotionMailing, State


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
    """Champs de l'e-mail d'un client, lus au moment de l'envoi."""
    promotion = mailing.promotion
    # La page « Nos offres du moment » ne montre que les promotions automatiques en cours.
    on_offers_page = promotion.is_automatic and promotion.state() == State.RUNNING
    return {
        "prénom": user.first_name,
        "message": mailing.message,
        "offre": _offer(promotion),
        "lien": site_url(reverse("offers" if on_offers_page else "country_list")),
        "désinscription": (
            "Vous recevez cet e-mail parce que vous avez accepté de recevoir nos offres. "
            f"Pour ne plus les recevoir, suivez ce lien :\n{unsubscribe_link(user)}"
        ),
    }


def _offer(promotion: Promotion) -> str:
    """Bloc de l'offre : remise, description, destinations, validité et code promo."""
    if promotion.starts_on > timezone.localdate():
        period = f"du {_day(promotion.starts_on)} au {_day(promotion.ends_on)}"
    else:
        period = f"jusqu'au {_day(promotion.ends_on)}"
    validity = f"Offre valable pour les demandes de voyage faites {period} inclus"
    if promotion.departure_from:
        validity += f", pour les départs du {_day(promotion.departure_from)} au {_day(promotion.departure_until)}"
    lines = [f"{promotion.name} : {promotion.discount_label} {promotion.base_label}."]
    if promotion.description:
        lines.append(promotion.description)
    lines += [f"Destinations concernées : {promotion.targets_label}.", f"{validity}."]
    if promotion.code:
        lines.append(
            f"Votre code promo : {promotion.code}. "
            "Saisissez-le dans le champ « Code promo » de votre demande de voyage."
        )
    return "\n".join(lines)


def _day(day) -> str:
    return date_format(day, "j F Y")
