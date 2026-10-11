"""Recherche d'un client par nom, prénom ou e-mail, sans tenir compte des accents ni des majuscules."""

from django.db.models import CharField, QuerySet, Value
from django.db.models.functions import Concat

from accounts.models import Role, User
from common.db import Normalize
from common.text import normalize


def search_words(query: str | None) -> list[str]:
    return normalize(query or "").split()


def matching_clients(words: list[str]) -> QuerySet[User]:
    """Clients dont le nom, le prénom ou l'e-mail contient tous les mots (issus de search_words).

    Filtrage fait par la base grâce à Normalize : aucun client n'est chargé pour rien.
    Sans mot, tous les clients sont gardés.
    """
    text = Concat("last_name", Value(" "), "first_name", Value(" "), "email", output_field=CharField())
    clients = User.objects.filter(role=Role.CLIENT).alias(search_text=Normalize(text))
    for word in words:
        clients = clients.filter(search_text__contains=word)
    return clients
