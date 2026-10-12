"""Chiffres du tableau de bord opérationnel (agents et administrateur), calculés à chaque affichage.

Chaque chiffre de commandes est compté avec les filtres de la liste des demandes (`filter_orders`) :
le lien du chiffre ouvre ainsi exactement les commandes comptées. Aucun montant ici.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from orders.models import OrderStatus
from orders.services.filtering import filter_orders
from reviews.services.moderation import pending_reviews

# « Les 7 prochains jours » : aujourd'hui compris, donc d'aujourd'hui à aujourd'hui + 6.
DEPARTURE_WINDOW_DAYS = 7


@dataclass(frozen=True)
class OrderFigure:
    count: int
    # Critères de la liste des demandes (mêmes noms que les champs de StaffOrderFilterForm).
    criteria: dict


@dataclass(frozen=True)
class OperationalFigures:
    pending: OrderFigure
    overdue: OrderFigure
    departures: OrderFigure
    reviews_to_moderate: int


def operational_figures(today: date | None = None) -> OperationalFigures:
    today = today or timezone.localdate()
    return OperationalFigures(
        pending=_order_figure({"status": OrderStatus.PENDING}),
        overdue=_order_figure({"status": OrderStatus.PENDING, "overdue": True}),
        departures=_order_figure({
            "status": OrderStatus.CONFIRMED,
            "departure_from": today,
            "departure_to": today + timedelta(days=DEPARTURE_WINDOW_DAYS - 1),
        }),
        reviews_to_moderate=pending_reviews().count(),
    )


def _order_figure(criteria: dict) -> OrderFigure:
    return OrderFigure(count=filter_orders(criteria).count(), criteria=criteria)
