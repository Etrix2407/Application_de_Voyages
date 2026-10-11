"""Outils de texte partagés par les applications (comparaison sans accents, montants, durées)."""

import unicodedata
from datetime import timedelta


def euros(amount) -> str:
    """Montant en euros à la française : « 1234,50 € »."""
    return f"{amount:.2f}".replace(".", ",") + " €"


def normalize(text: str) -> str:
    """Sans accents, sans majuscules ni espaces autour : « Pérou » devient « perou ».

    Sert aux comparaisons et recherches. SQLite ne sait pas ignorer les accents : dans une
    requête, utiliser son équivalent SQL common.db.Normalize.
    """
    decompose = unicodedata.normalize("NFKD", text.strip())
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


def duration_text(duration: timedelta) -> str:
    """Durée pour les messages : « 15 minutes », « une heure », « 48 heures », « 30 jours »."""
    minutes = int(duration.total_seconds()) // 60
    if minutes % 60:
        return f"{minutes} minutes"
    hours = minutes // 60
    if hours == 1:
        return "une heure"
    # Les délais annoncés en heures (24 h, 48 h) le restent ; les longues durées sont en jours.
    if hours % 24 == 0 and hours >= 72:
        return f"{hours // 24} jours"
    return f"{hours} heures"
