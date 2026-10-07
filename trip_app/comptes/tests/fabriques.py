"""Création de comptes pour les tests (partagée par toutes les applications)."""

from datetime import date

from django.contrib.auth import get_user_model

from comptes.models import Role

Utilisateur = get_user_model()

MOT_DE_PASSE = "voyage2026ok"


def creer_client(email="client@example.com", **champs):
    champs.setdefault("nom", "Dupont")
    champs.setdefault("prenom", "Marie")
    champs.setdefault("date_naissance", date(1955, 4, 12))
    return Utilisateur.objects.create_user(email, MOT_DE_PASSE, **champs)


def creer_agent(email="agent@example.com", **champs):
    champs.setdefault("nom", "Martin")
    champs.setdefault("prenom", "Luc")
    return Utilisateur.objects.create_user(email, MOT_DE_PASSE, role=Role.AGENT, **champs)


def creer_admin(email="gerante@example.com", **champs):
    champs.setdefault("nom", "Durand")
    champs.setdefault("prenom", "Anne")
    return Utilisateur.objects.create_superuser(email, MOT_DE_PASSE, **champs)
