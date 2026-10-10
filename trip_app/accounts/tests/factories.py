"""Création de comptes pour les tests (partagée par toutes les applications)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Role

User = get_user_model()

PASSWORD = "voyage2026ok"


def create_client(email="client@example.com", **fields):
    fields.setdefault("last_name", "Dupont")
    fields.setdefault("first_name", "Marie")
    fields.setdefault("birth_date", date(1955, 4, 12))
    # Adresse confirmée par défaut : un client non confirmé ne peut pas envoyer de demande.
    fields.setdefault("email_confirmed_at", timezone.now())
    return User.objects.create_user(email, PASSWORD, **fields)


def create_agent(email="agent@example.com", **fields):
    fields.setdefault("last_name", "Martin")
    fields.setdefault("first_name", "Luc")
    return User.objects.create_user(email, PASSWORD, role=Role.AGENT, **fields)


def create_admin(email="gerante@example.com", **fields):
    fields.setdefault("last_name", "Durand")
    fields.setdefault("first_name", "Anne")
    return User.objects.create_superuser(email, PASSWORD, **fields)
