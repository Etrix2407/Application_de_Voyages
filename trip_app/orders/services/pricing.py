"""Prix estimé d'une demande de voyage (« estimation, non contractuel »).

Formule : (prix indicatif de la destination + prix des activités) × voyageurs,
les enfants payant 50 %, y compris pour les activités. Une destination sans prix
indicatif est « sur devis » : l'estimation ne compte alors que les activités.
"""

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

CHILD_RATE = Decimal("0.5")
_CENT = Decimal("0.01")


def estimate_price(
    destination_price: Decimal | None,
    activity_prices: Iterable[Decimal],
    adults: int,
    children: int,
) -> Decimal:
    price_per_person = (destination_price or Decimal("0")) + sum(activity_prices, Decimal("0"))
    total = price_per_person * adults + price_per_person * CHILD_RATE * children
    return total.quantize(_CENT, rounding=ROUND_HALF_UP)
