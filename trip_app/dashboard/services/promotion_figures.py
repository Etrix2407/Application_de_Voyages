"""Résumé des promotions pour le tableau de pilotage ; le détail reste sur la page de chaque promotion.

Mêmes règles que les statistiques d'une promotion (orders/services/promotion_statistics.py) :
les commandes annulées sont exclues et la remise retenue est la plus récente.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from dashboard.services.order_figures import latest_discount
from dashboard.services.periods import Period
from orders.models import Order, OrderStatus
from promotions.models import Promotion


@dataclass(frozen=True)
class RunningPromotion:
    pk: int
    name: str
    order_count: int
    total_discount: Decimal


@dataclass(frozen=True)
class BestPromotion:
    pk: int
    name: str
    order_count: int


@dataclass(frozen=True)
class PromotionFigures:
    running: list[RunningPromotion]
    # Aucune commande avec promotion sur la période : None.
    best: BestPromotion | None


def promotion_figures(period: Period) -> PromotionFigures:
    return PromotionFigures(running=_running_promotions(), best=_best_promotion(period))


def _kept_orders():
    return Order.objects.exclude(status=OrderStatus.CANCELLED)


def _running_promotions() -> list[RunningPromotion]:
    """Promotions en cours aujourd'hui (pas selon la période choisie), du plus récent au plus ancien.

    Utilisations et remises sont cumulées depuis le début de la promotion, quelle que soit la période :
    une demande ne reçoit une promotion que pendant sa validité, toutes ses demandes comptent donc.
    """
    promotions = list(Promotion.objects.running().only("pk", "name"))
    # Un seul agrégat pour toutes les promotions en cours.
    rows = (
        _kept_orders()
        .filter(promotion__in=[promotion.pk for promotion in promotions])
        .order_by()
        .values("promotion")
        .annotate(order_count=Count("pk"), total_discount=Sum(latest_discount()))
    )
    figures = {row["promotion"]: row for row in rows}
    running = []
    for promotion in promotions:
        row = figures.get(promotion.pk, {})
        running.append(
            RunningPromotion(
                pk=promotion.pk,
                name=promotion.name,
                order_count=row.get("order_count", 0),
                total_discount=row.get("total_discount") or Decimal("0.00"),
            )
        )
    return running


def _best_promotion(period: Period) -> BestPromotion | None:
    """Promotion la plus utilisée par les commandes de la période ; à égalité, la plus récente."""
    row = (
        period.filter_orders(_kept_orders().filter(promotion__isnull=False))
        .order_by()
        .values("promotion", "promotion__name")
        .annotate(order_count=Count("pk"))
        .order_by("-order_count", "-promotion")
        .first()
    )
    if row is None:
        return None
    return BestPromotion(pk=row["promotion"], name=row["promotion__name"], order_count=row["order_count"])
