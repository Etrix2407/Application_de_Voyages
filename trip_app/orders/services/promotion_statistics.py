"""Statistiques d'une promotion : demandes qui l'ont utilisée, remises accordées, clients.

- Les demandes annulées sont exclues de tous les chiffres et listées à part.
- Remise d'une demande : la plus récente, celle de la confirmation si elle existe, sinon celle de la demande.
- Clients différents : comptés parmi les comptes connus. Une demande anonymisée (compte supprimé)
  ne permet pas de savoir de quel client il s'agit : elle est comptée à part.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from orders.models import Order, Status
from promotions.models import Promotion


@dataclass(frozen=True)
class PromotionStatistics:
    order_count: int
    total_discount: Decimal
    client_count: int
    anonymized_count: int
    orders: QuerySet
    cancelled_orders: QuerySet


def promotion_statistics(promotion: Promotion) -> PromotionStatistics:
    orders = (
        Order.objects.filter(promotion=promotion)
        # Calculé par la base : SQLite le rend sans décimales inutiles (50), d'où floatformat:2 à l'affichage.
        .annotate(latest_discount=Coalesce("confirmed_discount", "discount"))
        .select_related("client")
        .defer("remarks")
    )
    kept = orders.exclude(status=Status.CANCELLED)
    figures = kept.aggregate(
        order_count=Count("pk"),
        total_discount=Coalesce(Sum("latest_discount"), Decimal("0.00")),
        client_count=Count("client", distinct=True),
        anonymized_count=Count("pk", filter=Q(client__isnull=True)),
    )
    return PromotionStatistics(
        orders=kept, cancelled_orders=orders.filter(status=Status.CANCELLED), **figures
    )
