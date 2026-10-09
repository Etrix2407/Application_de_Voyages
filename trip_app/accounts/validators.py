"""Validateurs des données de compte."""

import re

from django.core.exceptions import ValidationError

# Numéro belge : 0 ou +32, puis 8 chiffres (fixe) ou 9 chiffres (mobile).
_BELGIAN_PHONE = re.compile(r"^(?:\+32|0)[1-9]\d{7,8}$")
# Numéro étranger : + et indicatif du pays, 8 à 15 chiffres au total (norme internationale).
_INTERNATIONAL_PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
_SEPARATORS = re.compile(r"[\s./()-]")


def normalize_phone(value: str) -> str:
    """Retire les séparateurs usuels ; le préfixe international 00 devient +."""
    digits = _SEPARATORS.sub("", value)
    return "+" + digits[2:] if digits.startswith("00") else digits


def validate_phone(value: str) -> None:
    """Numéro belge (0470 12 34 56) ou international (+33 6 12 34 56 78)."""
    number = normalize_phone(value)
    # Un numéro +32 est belge : il doit respecter le format belge.
    pattern = _BELGIAN_PHONE if number.startswith(("0", "+32")) else _INTERNATIONAL_PHONE
    if not pattern.match(number):
        raise ValidationError(
            "Saisissez un numéro valide : belge (0470 12 34 56) ou international avec l'indicatif "
            "du pays (+33 6 12 34 56 78).",
            code="invalid_phone",
        )


class LetterAndDigitValidator:
    """Exige au moins une lettre et au moins un chiffre dans le mot de passe."""

    def validate(self, password: str, user=None) -> None:
        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            raise ValidationError(
                "Le mot de passe doit contenir au moins une lettre et un chiffre.",
                code="password_without_letter_or_digit",
            )

    def get_help_text(self) -> str:
        return "Votre mot de passe doit contenir au moins une lettre et un chiffre."
