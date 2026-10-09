"""Création d'une demande de voyage par un client."""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from catalog.models import Destination
from orders.models import Order, OrderActivity, Status, StatusChange
from orders.services.pricing import Quote, estimate_price, price_parts
from orders.services.promotions import limit_problem
from promotions.services.discounts import Offer, PriceParts, discount_amount

# Garde-fou contre les envois en masse : largement au-dessus d'un usage normal.
MAX_ORDERS_PER_DAY = 10
NO_DISCOUNT = Decimal("0.00")


def parts_for(destination: Destination, activities, adults: int, children: int) -> PriceParts:
    return price_parts(destination.price_from, [activity.price_per_person for activity in activities], adults, children)


def quote_for(destination: Destination, activities, adults: int, children: int, discount=NO_DISCOUNT) -> Quote:
    before = estimate_price(
        destination.price_from, [activity.price_per_person for activity in activities], adults, children
    )
    return Quote(before, discount)


def price_at_current_rates(order: Order) -> Quote:
    """Prix d'une demande existante recalculé aux tarifs actuels du catalogue.

    La promotion figée dans la demande est ré-appliquée telle quelle (un pourcentage reste
    un pourcentage, un montant fixe reste le même montant), même si elle est terminée.
    """
    activities = [line.activity for line in order.activities.select_related("activity")]
    discount = NO_DISCOUNT
    if order.promotion:
        prices = parts_for(order.destination, activities, order.adults, order.children)
        discount = discount_amount(order.promotion, prices)
    return quote_for(order.destination, activities, order.adults, order.children, discount)


def find_pending_duplicates(client, destination: Destination, departure_date, return_date):
    """Demandes « En attente » du client pour la même destination aux mêmes dates."""
    return Order.objects.filter(
        client=client,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        status=Status.PENDING,
    )


def daily_limit_reached(client) -> bool:
    """Le client a déjà envoyé MAX_ORDERS_PER_DAY demandes ces dernières 24 heures (annulées comprises)."""
    since = timezone.now() - timedelta(days=1)
    return Order.objects.filter(client=client, created_at__gte=since).count() >= MAX_ORDERS_PER_DAY


class DailyLimitReached(Exception):
    """Trop de demandes envoyées ces dernières 24 heures."""


class AlreadySubmitted(Exception):
    """La même page de vérification a déjà été envoyée (double clic)."""

    def __init__(self, order: Order):
        super().__init__("Cette demande a déjà été envoyée.")
        self.order = order


class PromotionUnavailable(Exception):
    """La limite de la promotion a été atteinte au moment de l'enregistrement (ex. dernière utilisation)."""


def place_order(
    client, destination: Destination, data: dict, offer: Offer | None = None, submission_token=None
) -> Order:
    """Enregistre la demande « En attente » avec ses prix figés et son historique.

    `data` provient d'un formulaire validé (dates, voyageurs, activités, remarques) ; les règles
    du modèle sont tout de même revérifiées ici et lèvent ValidationError (rien n'est enregistré).
    `offer` est la promotion retenue (orders.services.promotions) : son nom et la remise sont figés.
    Un `submission_token` déjà utilisé lève AlreadySubmitted : la base garantit l'unicité,
    même si deux envois arrivent au même instant. Au-delà de MAX_ORDERS_PER_DAY demandes
    en 24 heures, lève DailyLimitReached. Si la limite de la promotion est atteinte au moment
    de l'enregistrement (dernière utilisation prise entre-temps), lève PromotionUnavailable.
    """
    if daily_limit_reached(client):
        raise DailyLimitReached
    try:
        return _create_order(client, destination, data, offer, submission_token)
    except IntegrityError:
        existing = Order.objects.filter(submission_token=submission_token).first() if submission_token else None
        if existing is None:
            raise
        raise AlreadySubmitted(existing) from None


@transaction.atomic
def _create_order(client, destination: Destination, data: dict, offer: Offer | None, submission_token) -> Order:
    # Limites revérifiées dans la transaction, qui détient déjà le verrou d'écriture (réglage
    # « IMMEDIATE » de settings.py) : de deux envois simultanés, le second voit le premier.
    if offer and limit_problem(offer.promotion, client):
        raise PromotionUnavailable
    activities = list(data["activities"])
    discount = offer.discount if offer else NO_DISCOUNT
    quote = quote_for(destination, activities, data["adults"], data["children"], discount)
    order = Order(
        submission_token=submission_token,
        client=client,
        destination=destination,
        destination_name=destination.name,
        country_name=destination.country.name,
        departure_date=data["departure_date"],
        return_date=data["return_date"],
        adults=data["adults"],
        children=data["children"],
        remarks=data["remarks"],
        destination_price=destination.price_from,
        estimated_price=quote.price,
        discount=quote.discount,
        promotion=offer.promotion if offer else None,
        promotion_name=offer.promotion.name if offer else "",
    )
    # L'unicité du jeton est laissée à la base : elle seule tranche entre deux envois simultanés.
    order.full_clean(validate_unique=False)
    order.save()
    lines = [
        OrderActivity(order=order, activity=activity, activity_name=activity.name, unit_price=activity.price_per_person)
        for activity in activities
    ]
    for line in lines:
        line.full_clean()
    OrderActivity.objects.bulk_create(lines)
    StatusChange.objects.create(
        order=order, status=Status.PENDING, author=client, author_name=StatusChange.CLIENT_AUTHOR, by_client=True
    )
    return order
