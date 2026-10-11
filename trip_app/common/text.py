"""Outils de texte partagés par les applications (comparaison sans accents, montants, durées)."""

import unicodedata
from datetime import timedelta


# Espace insécable : un montant n'est jamais coupé en fin de ligne.
NBSP = " "


def euros(amount) -> str:
    """Montant en euros à la française, milliers séparés : « 1 234,50 € »."""
    grouped = f"{amount:,.2f}".replace(",", NBSP).replace(".", ",")
    return f"{grouped}{NBSP}€"


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
    if minutes < 1:
        raise ValueError("Durée trop courte pour un message : une minute au moins.")
    if minutes % 60:
        return "une minute" if minutes == 1 else f"{minutes} minutes"
    hours = minutes // 60
    if hours == 1:
        return "une heure"
    # Les délais annoncés en heures (24 h, 48 h) le restent ; les longues durées sont en jours.
    if hours % 24 == 0 and hours >= 72:
        return f"{hours // 24} jours"
    return f"{hours} heures"
