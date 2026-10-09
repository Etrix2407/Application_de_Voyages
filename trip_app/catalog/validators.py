"""Validateurs des données du catalogue."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from .services.time_zones import is_known_time_zone


def validate_time_zone(name: str) -> None:
    if not is_known_time_zone(name):
        raise ValidationError("Choisissez un fuseau horaire de la liste.", code="unknown_time_zone")


# Ancien décalage saisi à la main : n'est plus utilisé que par la migration 0001.
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


# Photos des destinations : formats courants des appareils et téléphones, 5 Mo maximum.
PHOTO_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024


def validate_photo_size(photo) -> None:
    if photo.size > MAX_PHOTO_SIZE:
        raise ValidationError("La photo ne doit pas dépasser 5 Mo.", code="photo_too_large")
