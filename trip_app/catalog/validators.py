"""Validateurs des données du catalogue."""

from decimal import Decimal

from django.core.exceptions import ValidationError

OFFSET_MIN = Decimal("-12")
OFFSET_MAX = Decimal("14")


def validate_time_offset(value: Decimal) -> None:
    """Décalage en heures par rapport à la Belgique, par quart d'heure (ex. 5.5, 5.75)."""
    if not OFFSET_MIN <= value <= OFFSET_MAX:
        raise ValidationError(
            "Le décalage doit être compris entre -12 et +14 heures.", code="offset_out_of_range"
        )
    if (value * 4) % 1:
        raise ValidationError(
            "Le décalage doit être un multiple d'un quart d'heure (ex. 5.25, 5.5, 5.75).",
            code="offset_not_quarter_hour",
        )
