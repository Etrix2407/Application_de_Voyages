"""Charge des données de démonstration FICTIVES (développement uniquement).

Les pays, langues et monnaies sont imaginaires et marqués « Exemple » pour ne
jamais être confondus avec de vraies informations de voyage.
"""

import secrets
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogue.models import Activite, Categorie, Continent, Destination, Difficulte, Mois, Pays, Visa
from comptes.models import Role

PAYS = [
    {
        "nom": "Exemple — Pays des Lacs",
        "continent": Continent.EUROPE,
        "visa": Visa.NON_REQUIS,
        "decalage_ete": Decimal("0"),
        "decalage_hiver": Decimal("0"),
        "destinations": [
            ("Exemple — Ville des Ponts", Mois.MAI, Mois.SEPTEMBRE, Decimal("450")),
            ("Exemple — Vallée Verte", Mois.JUIN, Mois.AOUT, None),
        ],
        "activites": [
            ("Exemple — Visite du musée", Categorie.CULTURE, 120, Decimal("15"), Difficulte.FACILE, None, 0),
            ("Exemple — Croisière sur le lac", Categorie.DETENTE, 180, Decimal("40"), Difficulte.FACILE, None, 0),
            ("Exemple — Randonnée des crêtes", Categorie.SPORT, 360, Decimal("25"), Difficulte.DIFFICILE, 14, 1),
        ],
    },
    {
        "nom": "Exemple — Royaume des Épices",
        "continent": Continent.ASIE,
        "visa": Visa.E_VISA,
        "decalage_ete": Decimal("4.5"),
        "decalage_hiver": Decimal("5.5"),
        "destinations": [
            ("Exemple — Cité du Marché", Mois.NOVEMBRE, Mois.MARS, Decimal("1200")),
        ],
        "activites": [
            ("Exemple — Cours de cuisine", Categorie.GASTRONOMIE, 150, Decimal("55"), Difficulte.FACILE, None, 0),
            ("Exemple — Descente en rafting", Categorie.AVENTURE, 240, Decimal("90"), Difficulte.MOYEN, 12, None),
        ],
    },
]

# Pays désactivé : invisible pour les clients, visible dans la gestion du catalogue.
PAYS_DESACTIVE = {
    "nom": "Exemple — Île Fermée",
    "continent": Continent.OCEANIE,
    "visa": Visa.AVANT_DEPART,
    "decalage_ete": Decimal("10"),
    "decalage_hiver": Decimal("9"),
    "destinations": [],
    "activites": [],
}

COMPTES = [
    ("client.demo@example.com", Role.CLIENT, "Client", "Démo"),
    ("agent.demo@example.com", Role.AGENT, "Agent", "Démo"),
]


class Command(BaseCommand):
    help = "Charge des données de démonstration fictives (pays « Exemple » et comptes de test)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées : DJANGO_DEBUG doit valoir 1.")
        with transaction.atomic():
            for donnees in PAYS:
                self._creer_pays(donnees, actif=True)
            self._creer_pays(PAYS_DESACTIVE, actif=False)
            for compte in COMPTES:
                self._creer_compte(*compte)
        self.stdout.write(self.style.SUCCESS("Données de démonstration chargées."))

    def _creer_pays(self, donnees: dict, actif: bool) -> None:
        if Pays.objects.filter(nom=donnees["nom"]).exists():
            self.stdout.write(f"Déjà présent : {donnees['nom']}")
            return
        pays = Pays.objects.create(
            nom=donnees["nom"],
            continent=donnees["continent"],
            langue_principale="langue fictive",
            monnaie="monnaie fictive",
            description="Pays fictif de démonstration. Ces informations ne sont pas réelles.",
            visa=donnees["visa"],
            decalage_ete=donnees["decalage_ete"],
            decalage_hiver=donnees["decalage_hiver"],
            actif=actif,
        )
        destinations = [
            Destination.objects.create(
                pays=pays,
                nom=nom,
                description="Destination fictive de démonstration.",
                mois_debut=debut,
                mois_fin=fin,
                prix_a_partir_de=prix,
            )
            for nom, debut, fin, prix in donnees["destinations"]
        ]
        for nom, categorie, duree, prix, difficulte, age, index_destination in donnees["activites"]:
            Activite.objects.create(
                pays=pays,
                destination=destinations[index_destination] if index_destination is not None else None,
                nom=nom,
                description="Activité fictive de démonstration.",
                categorie=categorie,
                duree_minutes=duree,
                prix_par_personne=prix,
                difficulte=difficulte,
                age_minimum=age,
            )
        self.stdout.write(f"Créé : {pays.nom}")

    def _creer_compte(self, email: str, role: str, prenom: str, nom: str) -> None:
        Utilisateur = get_user_model()
        if Utilisateur.objects.filter(email=email).exists():
            self.stdout.write(f"Déjà présent : {email} (mot de passe inchangé)")
            return
        # Mot de passe aléatoire : jamais écrit dans le code ni dans le dépôt.
        mot_de_passe = secrets.token_urlsafe(9) + "1a"
        champs = {"date_naissance": date(1960, 1, 1)} if role == Role.CLIENT else {}
        Utilisateur.objects.create_user(
            email, mot_de_passe, nom=nom, prenom=prenom, role=role, **champs
        )
        self.stdout.write(f"Compte {role} : {email} / mot de passe : {mot_de_passe}")
