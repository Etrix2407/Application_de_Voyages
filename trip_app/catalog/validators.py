"""Validateurs des données du catalogue."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from .services.time_zones import is_known_time_zone


def validate_time_zone(name: str) -> None:
    if not is_known_time_zone(name):
        raise ValidationError("Choisissez un fuseau horaire de la liste.", code="unknown_time_zone")


# Ancien décalage saisi à la main : n'est plus utilisé que par la migration 0001, qui
# l'importe. À garder tant que cette migration existe, sinon elle ne peut plus être chargée.
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
# Un petit fichier peut cacher une image immense (« bombe de décompression ») : au-delà de
# 40 millions de pixels, la photo est refusée avant d'être décodée.
MAX_PHOTO_PIXELS = 40_000_000


def validate_photo_size(photo) -> None:
    if photo.size > MAX_PHOTO_SIZE:
        raise ValidationError("La photo ne doit pas dépasser 5 Mo.", code="photo_too_large")


def validate_photo_pixels(width: int, height: int) -> None:
    """Dimensions lues dans l'en-tête du fichier, avant tout décodage de l'image."""
    if width * height > MAX_PHOTO_PIXELS:
        raise ValidationError(
            "La photo est trop grande (plus de 40 millions de pixels). "
            "Réduisez-la avant de l'envoyer, par exemple à 4000 × 3000 pixels.",
            code="photo_too_many_pixels",
        )
