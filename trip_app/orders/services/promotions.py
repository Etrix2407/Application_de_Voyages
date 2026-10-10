"""Promotion appliquée à une nouvelle demande de voyage : automatique ou sur code.

- Pas de cumul : la meilleure remise en euros l'emporte (voir promotions.services.discounts).
- Un code saisi qui est battu par une promotion automatique n'est pas consommé.
- Limites : seules les demandes non annulées comptent (une annulation rend l'utilisation).
- Un code dont la promotion n'a pas encore commencé est « invalide » : les offres à venir
  ne sont pas révélées. Les codes invalides sont limités (10 par heure et par client).
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import Count, F, Q
from django.utils import timezone

from accounts.services.throttling import Limiter
from catalog.models import Destination
from orders.models import Order, Status
from promotions.models import Promotion, normalize_code
from common.text import euros
from promotions.services.discounts import (
    Offer,
    PriceParts,
    allows_departure,
    best_offer,
    covers,
    in_scope,
    offer_for,
)
from promotions.services.public import current_offers

INVALID_CODE = "Code invalide"
EXPIRED_CODE = "Ce code a expiré"
WRONG_DESTINATION = "Ce code ne s'applique pas à cette destination"
WRONG_DEPARTURE = "Ce code ne s'applique pas à ces dates de départ"
NOT_FOR_THIS_ORDER = "Ce code ne s'applique pas à cette demande"
ALREADY_USED = "Vous avez déjà utilisé ce code"
NO_LONGER_AVAILABLE = "Ce code n'est plus disponible"
TOO_MANY_WRONG_CODES = "Trop de codes incorrects ont été essayés. Réessayez dans une heure, ou appelez l'agence."

wrong_codes = Limiter("promo-codes", max_attempts=10, window_seconds=60 * 60)


@dataclass(frozen=True)
class PromotionChoice:
    """Résultat pour une demande : l'offre retenue et, le cas échéant, un message sur le code saisi."""

    offer: Offer | None = None
    code_error: str = ""
    code_note: str = ""

    @property
    def code_applied(self) -> bool:
        return self.offer is not None and not self.offer.promotion.is_automatic

    @property
    def code_message(self) -> str:
        """« Code appliqué : -100,00 € », au même format que la note sur une offre plus avantageuse."""
        return f"Code appliqué : -{euros(self.offer.discount)}" if self.code_applied else ""


def uses(promotion: Promotion, client=None) -> int:
    """Demandes non annulées qui ont utilisé la promotion (toutes, ou celles du client)."""
    orders = Order.objects.filter(promotion=promotion).exclude(status=Status.CANCELLED)
    if client is not None:
        orders = orders.filter(client=client)
    return orders.count()


def exhausted_promotions():
    """Promotions dont le maximum au total est atteint (demandes non annulées), en une requête."""
    return (
        Promotion.objects.filter(max_uses__isnull=False)
        .annotate(used=Count("orders", filter=~Q(orders__status=Status.CANCELLED)))
        .filter(used__gte=F("max_uses"))
        .values_list("pk", flat=True)
    )


def public_offers(today=None) -> list[Promotion]:
    """Promotions automatiques montrées au public : en cours et pas encore épuisées."""
    return current_offers(today, exclude=exhausted_promotions())


def limit_problem(promotion: Promotion, client) -> str:
    if promotion.max_uses_per_client and uses(promotion, client) >= promotion.max_uses_per_client:
        return ALREADY_USED
    if promotion.max_uses and uses(promotion) >= promotion.max_uses:
        return NO_LONGER_AVAILABLE
    return ""


def choose_promotion(
    client, destination: Destination, departure_date: date, prices: PriceParts, code: str = "", today=None
) -> PromotionChoice:
    today = today or timezone.localdate()
    automatic = best_offer(
        offer_for(promotion, prices)
        for promotion in Promotion.objects.running(today).automatic()
        if covers(promotion, destination, departure_date) and not limit_problem(promotion, client)
    )
    if not code:
        return PromotionChoice(automatic)

    attempts_key = str(client.pk)
    if wrong_codes.is_locked(attempts_key):
        return PromotionChoice(automatic, code_error=TOO_MANY_WRONG_CODES)
    promotion = Promotion.objects.filter(code=normalize_code(code)).first()
    problem = _code_problem(promotion, client, destination, departure_date, today)
    offer = None if problem else offer_for(promotion, prices)
    if problem == INVALID_CODE:
        wrong_codes.record(attempts_key)
    if offer is None:
        return PromotionChoice(automatic, code_error=problem or NOT_FOR_THIS_ORDER)

    if automatic and best_offer([automatic, offer]) is automatic:
        # Le code n'est pas consommé : le client pourra s'en servir pour une autre demande.
        better = "plus" if automatic.discount > offer.discount else "aussi"
        note = f"Une offre {better} avantageuse s'applique déjà : -{euros(automatic.discount)}"
        return PromotionChoice(automatic, code_note=note)
    return PromotionChoice(offer)


def _code_problem(promotion: Promotion | None, client, destination, departure_date, today) -> str:
    if promotion is None or (promotion.is_active and today < promotion.starts_on):
        return INVALID_CODE
    if not promotion.is_active:
        return NO_LONGER_AVAILABLE
    if today > promotion.ends_on:
        return EXPIRED_CODE
    if not in_scope(promotion, destination):
        return WRONG_DESTINATION
    if not allows_departure(promotion, departure_date):
        return WRONG_DEPARTURE
    return limit_problem(promotion, client)
