"""Calcul de la remise d'une promotion et choix de la meilleure.

- Pourcentage : proportionnel au montant de l'assiette.
- Montant fixe : une seule fois par demande, plafonné au montant de l'assiette.
- Le prix après remise ne descend donc jamais sous 0 €.
- Une remise de 0 € (ex. « sur les activités » sans activité) rend la promotion non applicable.
- Pas de cumul : la plus grande remise en euros l'emporte ; à égalité, la promotion
  créée le plus récemment.

Les montants reçus sont ceux de la demande, enfants à 50 % compris : la remise
s'applique après le demi-tarif enfant.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from catalog.models import Destination
from promotions.models import Base, Kind, Promotion, Scope

_CENT = Decimal("0.01")


@dataclass(frozen=True)
class PriceParts:
    """Prix d'une demande découpé selon les assiettes possibles."""

    stay: Decimal
    activities: Decimal

    @property
    def total(self) -> Decimal:
        return self.stay + self.activities


@dataclass(frozen=True)
class Offer:
    """Une promotion applicable et la remise en euros qu'elle donne."""

    promotion: Promotion
    discount: Decimal


def discount_amount(promotion: Promotion, prices: PriceParts) -> Decimal:
    base_amount = {Base.STAY: prices.stay, Base.ACTIVITIES: prices.activities, Base.TOTAL: prices.total}[
        promotion.base
    ]
    if promotion.kind == Kind.PERCENT:
        discount = base_amount * promotion.value / 100
    else:
        discount = min(promotion.value, base_amount)
    return discount.quantize(_CENT, rounding=ROUND_HALF_UP)


def in_scope(promotion: Promotion, destination: Destination) -> bool:
    if promotion.scope == Scope.COUNTRIES:
        return promotion.countries.filter(pk=destination.country_id).exists()
    if promotion.scope == Scope.DESTINATIONS:
        return promotion.destinations.filter(pk=destination.pk).exists()
    return True


def allows_departure(promotion: Promotion, departure_date: date) -> bool:
    """Le départ est dans la période autorisée, bornes incluses (sans période : tous les départs)."""
    if promotion.departure_from is None:
        return True
    return promotion.departure_from <= departure_date <= promotion.departure_until


def covers(promotion: Promotion, destination: Destination, departure_date: date) -> bool:
    return in_scope(promotion, destination) and allows_departure(promotion, departure_date)


def offer_for(promotion: Promotion, prices: PriceParts) -> Offer | None:
    """L'offre de cette promotion, ou None si elle ne donne aucune remise."""
    discount = discount_amount(promotion, prices)
    return Offer(promotion, discount) if discount > 0 else None


def best_offer(offers: Iterable[Offer | None]) -> Offer | None:
    """La plus grande remise ; à égalité, la promotion créée le plus récemment."""
    candidates = [offer for offer in offers if offer is not None]
    if not candidates:
        return None
    return max(candidates, key=lambda offer: (offer.discount, offer.promotion.created_at, offer.promotion.pk))
