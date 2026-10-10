"""Charge des données de démonstration FICTIVES (développement uniquement).

Les pays, langues et monnaies sont imaginaires et marqués « Exemple » pour ne
jamais être confondus avec de vraies informations de voyage.

La commande couvre toutes les versions (catalogue, promotions, demandes, avis) : elle est
rangée dans reviews, la dernière application de l'ordre `accounts ← catalog ← promotions
← orders ← reviews`, la seule qui peut utiliser toutes les autres.
"""

import secrets
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import Role
from catalog.models import Activity, Category, Continent, Destination, Difficulty, Month, Country, Visa
from orders.models import Order, Status, StatusChange
from orders.services.placing import parts_for, place_order
from orders.services.promotions import choose_promotion
from orders.services.status import cancel_by_client, confirm_by_staff
from promotions.models import Base, Kind, Promotion, Scope
from reviews.models import Review
from reviews.services.moderation import publish
from reviews.services.writing import ReviewNotAllowed, write_review

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

CLIENT_EMAIL = "client.demo@example.com"
AGENT_EMAIL = "agent.demo@example.com"

ACCOUNTS = [
    (CLIENT_EMAIL, Role.CLIENT, "Client", "Démo"),
    (AGENT_EMAIL, Role.AGENT, "Agent", "Démo"),
]

# Promotions en cours le jour de l'exécution : valables d'aujourd'hui à aujourd'hui + 180 jours.
PROMOTION_DAYS = 180
PROMO_CODE = "EXEMPLE10"
PROMOTIONS = [
    {
        "name": "Exemple — Offre des Lacs",
        "kind": Kind.PERCENT,
        "value": Decimal("10"),
        "scope": Scope.COUNTRIES,
        "country": "Exemple — Pays des Lacs",
        "code": None,
    },
    {
        "name": "Exemple — Code de bienvenue",
        "kind": Kind.FIXED,
        "value": Decimal("10"),
        "scope": Scope.CATALOG,
        "country": None,
        "code": PROMO_CODE,
    },
]

# Demandes du client démo, une par état. Les remarques servent aussi à reconnaître
# une demande déjà créée (relance sans doublon).
DEPARTURE_DELAY = timedelta(days=30)
STAY_LENGTH = timedelta(days=7)
TRIP_DONE_REMARKS = "Exemple — voyage terminé, avec un avis publié."
DEMO_ORDERS = [
    {
        "remarks": "Exemple — demande en attente de rappel par l'agence.",
        "destination": "Exemple — Ville des Ponts",
        "activities": ["Exemple — Visite du musée"],
        "code": "",
        "status": Status.PENDING,
    },
    {
        "remarks": f"Exemple — demande confirmée avec le code promo {PROMO_CODE}.",
        "destination": "Exemple — Cité du Marché",
        "activities": ["Exemple — Cours de cuisine"],
        "code": PROMO_CODE,
        "status": Status.CONFIRMED,
    },
    {
        "remarks": "Exemple — demande annulée par le client.",
        "destination": "Exemple — Vallée Verte",
        "activities": ["Exemple — Croisière sur le lac"],
        "code": "",
        "status": Status.CANCELLED,
    },
    {
        "remarks": TRIP_DONE_REMARKS,
        "destination": "Exemple — Cité du Marché",
        "activities": [],
        "code": "",
        "status": Status.CONFIRMED,
    },
]
CANCEL_REASON = "Exemple — projet reporté."
# Recul appliqué à la demande au voyage terminé (voir _move_to_past) : plus long que
# DEPARTURE_DELAY + STAY_LENGTH, pour que la date de retour soit passée.
TRIP_DONE_SHIFT = timedelta(days=60)

REVIEW = {
    "rating": 5,
    "title": "Exemple — Séjour réussi",
    "comment": "Exemple — avis fictif de démonstration.",
}


class Command(BaseCommand):
    help = (
        "Charge des données de démonstration fictives (pays « Exemple », comptes de test, "
        "promotions, demandes de voyage et avis)."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Données de démonstration refusées : DJANGO_DEBUG doit valoir 1.")
        User = get_user_model()
        with transaction.atomic():
            for data in COUNTRIES:
                self._create_country(data, active=True)
            self._create_country(INACTIVE_COUNTRY, active=False)
            for account in ACCOUNTS:
                self._create_account(*account)
            for data in PROMOTIONS:
                self._create_promotion(data)
            client = User.objects.get(email=CLIENT_EMAIL)
            agent = User.objects.get(email=AGENT_EMAIL)
            for data in DEMO_ORDERS:
                self._create_order(data, client, agent)
            self._create_review(client)
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

    def _create_promotion(self, data: dict) -> None:
        if Promotion.objects.filter(name=data["name"]).exists():
            self.stdout.write(f"Déjà présent : {data['name']}")
            return
        today = timezone.localdate()
        promotion = Promotion(
            name=data["name"],
            description="Promotion fictive de démonstration.",
            kind=data["kind"],
            value=data["value"],
            scope=data["scope"],
            base=Base.TOTAL,
            starts_on=today,
            ends_on=today + timedelta(days=PROMOTION_DAYS),
            code=data["code"],
        )
        promotion.full_clean()
        promotion.save()
        if data["country"]:
            promotion.countries.add(Country.objects.get(name=data["country"]))
        # Pas d'entrée d'historique : l'historique exige un administrateur comme auteur et la
        # démonstration n'en crée pas. La fiche affiche alors « Créée par — » et « Aucun historique ».
        self.stdout.write(f"Créé : {promotion.name}")

    def _create_order(self, data: dict, client, agent) -> None:
        """Demande créée et traitée par les services, comme dans l'application."""
        if Order.objects.filter(client=client, remarks=data["remarks"]).exists():
            self.stdout.write(f"Déjà présent : {data['remarks']}")
            return
        order = _place_order(client, data)
        if data["status"] == Status.CONFIRMED:
            confirm_by_staff(order, agent)
        elif data["status"] == Status.CANCELLED:
            cancel_by_client(order, CANCEL_REASON)
        if data["remarks"] == TRIP_DONE_REMARKS:
            _move_to_past(order)
        self.stdout.write(f"Créé : {data['remarks']}")

    def _create_review(self, client) -> None:
        """Avis écrit par le client démo puis publié (modération), sur son voyage terminé."""
        order = Order.objects.get(client=client, remarks=TRIP_DONE_REMARKS)
        if Review.objects.filter(order=order).exists():
            self.stdout.write(f"Déjà présent : avis « {REVIEW['title']} »")
            return
        try:
            review = write_review(client, Review(order=order, **REVIEW))
        except ReviewNotAllowed:
            self.stdout.write(f"Avis non créé : la demande « {TRIP_DONE_REMARKS} » ne peut pas recevoir d'avis.")
            return
        publish(review)
        self.stdout.write(f"Créé : avis publié « {review.title} »")


def _place_order(client, data: dict) -> Order:
    destination = Destination.objects.get(name=data["destination"])
    activities = list(Activity.objects.filter(country=destination.country, name__in=data["activities"]))
    departure = timezone.localdate() + DEPARTURE_DELAY
    adults, children = 2, 0
    # Même choix de promotion que la page de demande : automatique, ou code saisi s'il est meilleur.
    prices = parts_for(destination, activities, adults, children)
    choice = choose_promotion(client, destination, departure, prices, code=data["code"])
    order_data = {
        "departure_date": departure,
        "return_date": departure + STAY_LENGTH,
        "adults": adults,
        "children": children,
        "activities": activities,
        "remarks": data["remarks"],
    }
    return place_order(client, destination, order_data, choice.offer)


def _move_to_past(order: Order) -> None:
    """Recule de TRIP_DONE_SHIFT les dates de la demande, du voyage et de l'historique.

    Aucun service ne crée de voyage terminé : une nouvelle demande part au moins 7 jours
    plus tard et une demande au départ passé ne se confirme plus. La demande est donc
    créée et confirmée normalement (prix figés, empreinte, historique), puis tout est
    reculé du même nombre de jours : l'ordre demande → confirmation → départ → retour
    est conservé, et la date de retour devient passée (condition d'un avis).
    """
    Order.objects.filter(pk=order.pk).update(
        departure_date=order.departure_date - TRIP_DONE_SHIFT,
        return_date=order.return_date - TRIP_DONE_SHIFT,
        created_at=order.created_at - TRIP_DONE_SHIFT,
    )
    StatusChange.objects.filter(order=order).update(changed_at=F("changed_at") - TRIP_DONE_SHIFT)
