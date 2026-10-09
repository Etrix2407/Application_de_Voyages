"""Recherche d'un client par nom, prénom ou e-mail, sans tenir compte des accents ni des majuscules."""

from accounts.models import User
from common.text import normalize


def search_words(query: str | None) -> list[str]:
    return normalize(query or "").split()


def client_matches(client: User, words: list[str]) -> bool:
    """Tous les mots (issus de search_words) figurent dans le nom, le prénom ou l'e-mail.

    Comparaison en Python : SQLite ne sait pas ignorer les accents.
    """
    text = normalize(f"{client.last_name} {client.first_name} {client.email}")
    return all(word in text for word in words)
