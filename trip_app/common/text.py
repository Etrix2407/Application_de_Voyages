"""Outils de texte partagés par les applications (comparaison sans accents, montants)."""

import unicodedata


def euros(amount) -> str:
    """Montant en euros à la française : « 1234,50 € »."""
    return f"{amount:.2f}".replace(".", ",") + " €"


def normalize(text: str) -> str:
    """Sans accents, sans majuscules ni espaces autour : « Pérou » devient « perou ».

    Sert aux comparaisons et recherches : SQLite ne sait pas ignorer les accents.
    """
    decompose = unicodedata.normalize("NFKD", text.strip())
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()
