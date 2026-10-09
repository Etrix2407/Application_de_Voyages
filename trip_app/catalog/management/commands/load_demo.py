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

from catalog.models import Activity, Category, Continent, Destination, Difficulty, Month, Country, Visa
from accounts.models import Role

COUNTRIES = [
    {
        "name": "Exemple — Pays des Lacs",
        "continent": Continent.EUROPE,
        "visa": Visa.NOT_REQUIRED,
        "time_zone": "Europe/Brussels",
        "destinations": [
            ("Exemple — Ville des Ponts", Month.MAY, Month.SEPTEMBER, Decimal("450")),
            ("Exemple — Vallée Verte", Month.JUNE, Month.AUGUST, None),
        ],
        "activities": [
            ("Exemple — Visite du musée", Category.CULTURE, 120, Decimal("15"), Difficulty.EASY, None, 0),
            ("Exemple — Croisière sur le lac", Category.RELAXATION, 180, Decimal("40"), Difficulty.EASY, None, 0),
            ("Exemple — Randonnée des crêtes", Category.SPORT, 360, Decimal("25"), Difficulty.HARD, 14, 1),
        ],
    },
    {
        "name": "Exemple — Royaume des Épices",
        "continent": Continent.ASIA,
        "visa": Visa.E_VISA,
        "time_zone": "Asia/Kolkata",
        "destinations": [
            ("Exemple — Cité du Marché", Month.NOVEMBER, Month.MARCH, Decimal("1200")),
        ],
        "activities": [
            ("Exemple — Cours de cuisine", Category.GASTRONOMY, 150, Decimal("55"), Difficulty.EASY, None, 0),
            ("Exemple — Descente en rafting", Category.ADVENTURE, 240, Decimal("90"), Difficulty.MEDIUM, 12, None),
        ],
    },
]

# Pays désactivé : invisible pour les clients, visible dans la gestion du catalogue.
INACTIVE_COUNTRY = {
    "name": "Exemple — Île Fermée",
    "continent": Continent.OCEANIA,
    "visa": Visa.BEFORE_DEPARTURE,
    "time_zone": "Pacific/Noumea",
    "destinations": [],
    "activities": [],
}

ACCOUNTS = [
    ("client.demo@example.com", Role.CLIENT, "Client", "Démo"),
    ("agent.demo@example.com", Role.AGENT, "Agent", "Démo"),
]


class Command(BaseCommand):
    help = "Charge des données de démonstration fictives (pays « Exemple » et comptes de test)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées : DJANGO_DEBUG doit valoir 1.")
        with transaction.atomic():
            for data in COUNTRIES:
                self._create_country(data, active=True)
            self._create_country(INACTIVE_COUNTRY, active=False)
            for account in ACCOUNTS:
                self._create_account(*account)
        self.stdout.write(self.style.SUCCESS("Données de démonstration chargées."))

    def _create_country(self, data: dict, active: bool) -> None:
        if Country.objects.filter(name=data["name"]).exists():
            self.stdout.write(f"Déjà présent : {data['name']}")
            return
        country = Country.objects.create(
            name=data["name"],
            continent=data["continent"],
            main_language="langue fictive",
            currency="monnaie fictive",
            description="Pays fictif de démonstration. Ces informations ne sont pas réelles.",
            visa=data["visa"],
            time_zone=data["time_zone"],
            active=active,
        )
        destinations = [
            Destination.objects.create(
                country=country,
                name=name,
                description="Destination fictive de démonstration.",
                start_month=start,
                end_month=end,
                price_from=price,
            )
            for name, start, end, price in data["destinations"]
        ]
        for name, category, duration, price, difficulty, age, destination_index in data["activities"]:
            Activity.objects.create(
                country=country,
                destination=destinations[destination_index] if destination_index is not None else None,
                name=name,
                description="Activité fictive de démonstration.",
                category=category,
                duration_minutes=duration,
                price_per_person=price,
                difficulty=difficulty,
                minimum_age=age,
            )
        self.stdout.write(f"Créé : {country.name}")

    def _create_account(self, email: str, role: str, first_name: str, last_name: str) -> None:
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Déjà présent : {email} (mot de passe inchangé)")
            return
        # Mot de passe aléatoire : jamais écrit dans le code ni dans le dépôt.
        password = secrets.token_urlsafe(9) + "1a"
        fields = {"birth_date": date(1960, 1, 1)} if role == Role.CLIENT else {}
        User.objects.create_user(
            email, password, last_name=last_name, first_name=first_name, role=role, **fields
        )
        self.stdout.write(f"Compte {role} : {email} / mot de passe : {password}")
