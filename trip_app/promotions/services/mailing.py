"""Envoi d'une promotion par e-mail aux clients consentants (v5), décidé par l'administrateur.

L'envoi est seulement programmé : un e-mail par client est mis en attente dans le journal, puis
la commande planifiée process_emails les envoie à son prochain passage (5 minutes au plus).
Le message est construit à ce moment-là (email_rebuilders.py) : un client qui se désinscrit
entre-temps ne reçoit rien.

Avant l'envoi, l'administrateur confirme sur une page qui montre le nombre de clients et un aperçu
(mailing_preview) ; le jeton de cette page empêche de programmer deux fois le même envoi.
"""

from django.db import IntegrityError, transaction
from django.db.models import prefetch_related_objects
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import User
from accounts.services.email_texts import render_email
from accounts.services.emails import queue_emails, site_url
from accounts.services.unsubscribe import unsubscribe_link
from promotions.models import Promotion, PromotionEmail, PromotionMailing, PromotionState
from promotions.services.public import offers_something, visible_targets

# Aperçu avant l'envoi : chaque client lit son prénom et son propre lien de désinscription.
PREVIEW_FIRST_NAME = "Marie"
PREVIEW_UNSUBSCRIBE_LINK = "[lien personnel de désinscription]"


class NoRecipients(Exception):
    """Aucun client ne peut recevoir l'envoi (consentement, adresse confirmée, compte actif)."""


class AlreadySent(Exception):
    """Cet envoi a déjà été programmé (même jeton d'envoi) : rien n'est envoyé une seconde fois."""

    def __init__(self, mailing: PromotionMailing):
        super().__init__(mailing.pk)
        self.mailing = mailing


def can_be_mailed(promotion: Promotion) -> bool:
    """En cours ou à venir, et vise encore un pays ou une destination proposé.

    Les pays et destinations visés sont préchargés ici avec visible_targets s'ils ne le sont pas
    déjà (aucune requête de plus sinon) : un élément désactivé n'est jamais compté ni cité.
    """
    if promotion.state() not in (PromotionState.RUNNING, PromotionState.UPCOMING):
        return False
    prefetch_related_objects([promotion], *visible_targets(promotion.scope))
    return offers_something(promotion)


def mailable_promotions(exclude=()) -> list[Promotion]:
    """Promotions que l'administrateur peut envoyer, de la plus proche à la plus lointaine.

    `exclude` : promotions épuisées (maximum au total atteint). Ce sont les demandes qui le disent,
    donc l'appelant les donne (voir orders.services.promotions.exhausted_promotions).
    """
    candidates = (
        Promotion.objects.filter(is_active=True, ends_on__gte=timezone.localdate())
        .exclude(pk__in=exclude)
        .prefetch_related(*visible_targets())
        .order_by("starts_on", "name", "pk")
    )
    return [promotion for promotion in candidates if can_be_mailed(promotion)]


def send_promotion_mailing(
    promotion: Promotion, message: str, author: User, submission_token=None
) -> PromotionMailing:
    """Programme l'envoi à tous les clients consentants ; lève NoRecipients s'il n'y en a aucun.

    Un `submission_token` déjà utilisé (double clic, formulaire renvoyé) lève AlreadySent : la base
    garantit l'unicité, même si deux envois arrivent au même instant. Les clients ne reçoivent
    donc l'e-mail qu'une fois.
    """
    try:
        return _create_mailing(promotion, message, author, submission_token)
    except IntegrityError:
        existing = (
            PromotionMailing.objects.filter(submission_token=submission_token).first() if submission_token else None
        )
        if existing is None:
            raise
        raise AlreadySent(existing) from None


@transaction.atomic
def _create_mailing(promotion: Promotion, message: str, author: User, submission_token) -> PromotionMailing:
    recipients = list(User.objects.promotion_recipients().only("pk", "email"))
    if not recipients:
        raise NoRecipients
    mailing = PromotionMailing.objects.create(
        promotion=promotion,
        message=message,
        author=author,
        author_name=author.get_full_name(),
        recipients_count=len(recipients),
        submission_token=submission_token,
    )
    queue_emails(recipients, PromotionEmail.PROMOTION, promotion_mailing_number=mailing.pk)
    return mailing


def mailing_preview(promotion: Promotion, message: str) -> tuple[str, str]:
    """Objet et texte de l'e-mail, avant l'envoi. Prénom et lien de désinscription : des exemples."""
    prefetch_related_objects([promotion], *visible_targets(promotion.scope))
    rendered = render_email(
        PromotionEmail.PROMOTION, _email_fields(promotion, message, PREVIEW_FIRST_NAME, PREVIEW_UNSUBSCRIBE_LINK)
    )
    return rendered.subject, rendered.text


def promotion_email_context(mailing: PromotionMailing, user: User) -> dict:
    """Champs de l'e-mail d'un client, lus au moment de l'envoi."""
    return _email_fields(mailing.promotion, mailing.message, user.first_name, unsubscribe_link(user))


def _email_fields(promotion: Promotion, message: str, first_name: str, unsubscribe: str) -> dict:
    # La page « Nos offres du moment » ne montre que les promotions automatiques en cours.
    on_offers_page = promotion.is_automatic and promotion.state() == PromotionState.RUNNING
    return {
        "prénom": first_name,
        "message": message,
        "offre": _offer(promotion),
        "lien": site_url(reverse("offers" if on_offers_page else "country_list")),
        "désinscription": (
            "Vous recevez cet e-mail parce que vous avez accepté de recevoir nos offres. "
            f"Pour ne plus les recevoir, suivez ce lien :\n{unsubscribe}"
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
