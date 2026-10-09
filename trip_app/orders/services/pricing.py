"""Prix estimé d'une demande de voyage (« estimation, non contractuel »).

Formule : (prix indicatif de la destination + prix des activités) × voyageurs,
les enfants payant 50 %, y compris pour les activités. Une destination sans prix
indicatif est « sur devis » : l'estimation ne compte alors que les activités.

Une promotion éventuelle est ensuite déduite (v4) : la remise s'applique après le
demi-tarif enfant, sur la partie du prix choisie par la promotion (séjour, activités, total).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from promotions.services.discounts import PriceParts

CHILD_RATE = Decimal("0.5")
_CENT = Decimal("0.01")


def price_parts(
    destination_price: Decimal | None,
    activity_prices: Iterable[Decimal],
    adults: int,
    children: int,
) -> PriceParts:
    travellers = adults + CHILD_RATE * children
    return PriceParts(
        stay=(destination_price or Decimal("0")) * travellers,
        activities=sum(activity_prices, Decimal("0")) * travellers,
    )


def estimate_price(
    destination_price: Decimal | None,
    activity_prices: Iterable[Decimal],
    adults: int,
    children: int,
) -> Decimal:
    total = price_parts(destination_price, activity_prices, adults, children).total
    return total.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Quote:
    """Prix avant remise, remise et prix après remise (jamais sous 0 €)."""

    price_before_discount: Decimal
    discount: Decimal = Decimal("0.00")

    @property
    def price(self) -> Decimal:
        return max(self.price_before_discount - self.discount, Decimal("0.00"))
