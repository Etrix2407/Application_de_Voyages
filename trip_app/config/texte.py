"""Outils de texte partagés par les applications."""

import unicodedata


def normaliser(texte: str) -> str:
    """Sans accents, sans majuscules ni espaces autour : « Pérou » devient « perou ».

    Sert aux comparaisons et recherches : SQLite ne sait pas ignorer les accents.
    """
    decompose = unicodedata.normalize("NFKD", texte.strip())
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()
