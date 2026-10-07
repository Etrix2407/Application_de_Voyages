"""Validateurs des données du catalogue."""

from decimal import Decimal

from django.core.exceptions import ValidationError

DECALAGE_MIN = Decimal("-12")
DECALAGE_MAX = Decimal("14")


def valider_decalage_horaire(valeur: Decimal) -> None:
    """Décalage en heures par rapport à la Belgique, par quart d'heure (ex. 5.5, 5.75)."""
    if not DECALAGE_MIN <= valeur <= DECALAGE_MAX:
        raise ValidationError(
            "Le décalage doit être compris entre -12 et +14 heures.", code="decalage_hors_limites"
        )
    if (valeur * 4) % 1:
        raise ValidationError(
            "Le décalage doit être un multiple d'un quart d'heure (ex. 5.25, 5.5, 5.75).",
            code="decalage_non_quart_heure",
        )
