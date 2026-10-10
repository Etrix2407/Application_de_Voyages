"""Recherche d'un client par nom, prénom ou e-mail, sans tenir compte des accents ni des majuscules."""

from django.db.models import CharField, QuerySet, Value
from django.db.models.functions import Concat

from accounts.models import Role, User
from common.db import Normalize
from common.text import normalize


def search_words(query: str | None) -> list[str]:
    return normalize(query or "").split()


def client_matches(client: User, words: list[str]) -> bool:
    """Tous les mots (issus de search_words) figurent dans le nom, le prénom ou l'e-mail.

    Comparaison en Python : SQLite ne sait pas ignorer les accents.
    """
    text = normalize(f"{client.last_name} {client.first_name} {client.email}")
    return all(word in text for word in words)


def matching_clients(words: list[str]) -> QuerySet[User]:
    """Mêmes règles que client_matches, mais appliquées par la base (sous-requête, aucun client chargé)."""
    text = Concat("last_name", Value(" "), "first_name", Value(" "), "email", output_field=CharField())
    clients = User.objects.filter(role=Role.CLIENT).alias(search_text=Normalize(text))
    for word in words:
        clients = clients.filter(search_text__contains=word)
    return clients
