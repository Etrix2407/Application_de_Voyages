"""Création de comptes pour les tests (partagée par toutes les applications)."""

from datetime import date

from django.contrib.auth import get_user_model

from accounts.models import Role

User = get_user_model()

PASSWORD = "voyage2026ok"


def create_client(email="client@example.com", **fields):
    fields.setdefault("last_name", "Dupont")
    fields.setdefault("first_name", "Marie")
    fields.setdefault("birth_date", date(1955, 4, 12))
    return User.objects.create_user(email, PASSWORD, **fields)


def create_agent(email="agent@example.com", **fields):
    fields.setdefault("last_name", "Martin")
    fields.setdefault("first_name", "Luc")
    return User.objects.create_user(email, PASSWORD, role=Role.AGENT, **fields)


def create_admin(email="gerante@example.com", **fields):
    fields.setdefault("last_name", "Durand")
    fields.setdefault("first_name", "Anne")
    return User.objects.create_superuser(email, PASSWORD, **fields)
