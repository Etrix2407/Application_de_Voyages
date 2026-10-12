"""Classements du tableau de pilotage : ce qui est le plus (et le moins) demandé sur la période.

- Destinations et pays : commandes confirmées seulement, avec leur montant estimé (voir order_figures).
  Regroupés par l'objet du catalogue et affichés sous leur nom actuel : une destination renommée
  depuis la commande garde toutes ses commandes.
- Activités : commandes non annulées (en attente ou confirmées) qui les contiennent. Une demande en
  attente montre déjà l'intérêt du client ; une demande annulée est écartée, comme dans les statistiques
  des promotions.
- Bas du classement : destinations actives seulement (destination et pays actifs, comme le catalogue
  public), zéro compris : une destination jamais demandée apparaît avec 0 commande.
- Égalité : départage par nom, puis par identifiant, pour un ordre stable.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum

from catalog.models import Destination
from dashboard.services.order_figures import latest_price
from dashboard.services.periods import Period
from orders.models import Order, OrderActivity, OrderStatus

RANKING_SIZE = 5


@dataclass(frozen=True)
class RankedItem:
    pk: int
    name: str
    order_count: int
    # Pays de la destination ou de l'activité : deux homonymes restent distincts. Vide pour un pays.
    country_name: str = ""
    # Montant estimé des commandes confirmées ; None quand le classement ne le donne pas.
    estimated_amount: Decimal | None = None


@dataclass(frozen=True)
class Rankings:
    destinations: list[RankedItem]
    countries: list[RankedItem]
    activities: list[RankedItem]
    least_requested: list[RankedItem]


def build_rankings(period: Period) -> Rankings:
    confirmed = period.filter_orders(Order.objects.filter(status=OrderStatus.CONFIRMED))
    not_cancelled = period.filter_orders(Order.objects.exclude(status=OrderStatus.CANCELLED))
    return Rankings(
        destinations=_top_destinations(confirmed),
        countries=_top_countries(confirmed),
        activities=_top_activities(not_cancelled),
        least_requested=_least_requested_destinations(confirmed),
    )


def _top_destinations(confirmed: QuerySet) -> list[RankedItem]:
    rows = (
        confirmed.values("destination", "destination__name", "destination__country__name")
        .annotate(order_count=Count("pk"), estimated_amount=Sum(latest_price()))
        .order_by("-order_count", "destination__name", "destination")[:RANKING_SIZE]
    )
    return [
        RankedItem(
            pk=row["destination"],
            name=row["destination__name"],
            country_name=row["destination__country__name"],
            order_count=row["order_count"],
            estimated_amount=row["estimated_amount"],
        )
        for row in rows
    ]


def _top_countries(confirmed: QuerySet) -> list[RankedItem]:
    rows = (
        confirmed.values("destination__country", "destination__country__name")
        .annotate(order_count=Count("pk"), estimated_amount=Sum(latest_price()))
        .order_by("-order_count", "destination__country__name", "destination__country")[:RANKING_SIZE]
    )
    return [
        RankedItem(
            pk=row["destination__country"],
            name=row["destination__country__name"],
            order_count=row["order_count"],
            estimated_amount=row["estimated_amount"],
        )
        for row in rows
    ]


def _top_activities(orders: QuerySet) -> list[RankedItem]:
    # Une activité figure au plus une fois par commande (contrainte d'unicité) : une ligne = une commande.
    rows = (
        OrderActivity.objects.filter(order__in=orders)
        .values("activity", "activity__name", "activity__country__name")
        .annotate(order_count=Count("pk"))
        .order_by("-order_count", "activity__name", "activity")[:RANKING_SIZE]
    )
    return [
        RankedItem(
            pk=row["activity"],
            name=row["activity__name"],
            country_name=row["activity__country__name"],
            order_count=row["order_count"],
        )
        for row in rows
    ]


def _least_requested_destinations(confirmed: QuerySet) -> list[RankedItem]:
    destinations = (
        Destination.objects.visible()
        .annotate(order_count=Count("orders", filter=Q(orders__in=confirmed)))
        .select_related("country")
        .order_by("order_count", "name", "pk")[:RANKING_SIZE]
    )
    return [
        RankedItem(
            pk=destination.pk,
            name=destination.name,
            country_name=destination.country.name,
            order_count=destination.order_count,
        )
        for destination in destinations
    ]
