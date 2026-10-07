"""Validateurs des données de compte."""

import re

from django.core.exceptions import ValidationError

# Numéro belge : 0 ou +32 ou 0032, puis 8 chiffres (fixe) ou 9 chiffres (mobile).
_TELEPHONE_BELGE = re.compile(r"^(?:\+32|0032|0)[1-9]\d{7,8}$")
_SEPARATEURS = re.compile(r"[\s./-]")


def normaliser_telephone(valeur: str) -> str:
    """Retire les séparateurs usuels (espaces, points, barres, tirets)."""
    return _SEPARATEURS.sub("", valeur)


def valider_telephone_belge(valeur: str) -> None:
    if not _TELEPHONE_BELGE.match(normaliser_telephone(valeur)):
        raise ValidationError(
            "Saisissez un numéro belge valide, par exemple 0470 12 34 56 ou +32 2 123 45 67.",
            code="telephone_invalide",
        )


class LettreEtChiffreValidator:
    """Exige au moins une lettre et au moins un chiffre dans le mot de passe."""

    def validate(self, password: str, user=None) -> None:
        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            raise ValidationError(
                "Le mot de passe doit contenir au moins une lettre et un chiffre.",
                code="mot_de_passe_sans_lettre_ou_chiffre",
            )

    def get_help_text(self) -> str:
        return "Votre mot de passe doit contenir au moins une lettre et un chiffre."
