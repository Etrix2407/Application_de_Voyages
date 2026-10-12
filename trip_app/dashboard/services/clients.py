"""Chiffres des clients du tableau de pilotage (Recap 6).

- Un compte ne compte comme « créé » qu'une fois son adresse confirmée, qu'il existe encore ou qu'il
  ait été supprimé (trace anonyme DeletedClientAccount) : supprimer un compte ne change pas les
  chiffres d'une période passée. Un compte jamais confirmé ne compte nulle part.
- Comptes créés : jour de création à Bruxelles. La base de date choisie (commande ou départ) ne
  s'applique pas ici : elle ne concerne que les commandes.
- Clients inscrits : comptes clients actifs à l'adresse confirmée, aujourd'hui (pas de période).
- « A passé une commande » : au moins une commande, quel qu'en soit l'état et à n'importe quelle date.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Exists, OuterRef, Q

from accounts.models import DeletedClientAccount, Role, User
from common.text import NBSP
from dashboard.services.comparison import Comparison, compare
from dashboard.services.periods import Period
from orders.models import Order


@dataclass(frozen=True)
class ClientFigures:
    created: int
    created_comparison: Comparison
    registered: int
    registered_with_orders: int
    # Déjà mis en forme : « 42 % », ou « — » sans compte créé sur la période.
    conversion_rate: str


def client_figures(period: Period) -> ClientFigures:
    created, converted = _created_accounts(period)
    previous_created, _ = _created_accounts(period.previous())
    registered = _confirmed_clients().filter(is_active=True).aggregate(
        total=Count("pk"), with_orders=Count("pk", filter=Q(has_orders=True))
    )
    return ClientFigures(
        created=created,
        created_comparison=compare(created, previous_created),
        registered=registered["total"],
        registered_with_orders=registered["with_orders"],
        conversion_rate=_percentage(converted, created),
    )


def _confirmed_clients():
    """Comptes clients à l'adresse confirmée, avec `has_orders` (au moins une commande)."""
    return User.objects.filter(role=Role.CLIENT, email_confirmed_at__isnull=False).alias(
        has_orders=Exists(Order.objects.filter(client=OuterRef("pk")))
    )


def _created_accounts(period: Period) -> tuple[int, int]:
    """Comptes créés sur la période (existants et supprimés), et combien ont passé une commande."""
    # __date : jour dans le fuseau du site (Bruxelles).
    created_in_period = Q(date_joined__date__range=(period.start, period.end))
    live = _confirmed_clients().filter(created_in_period).aggregate(
        total=Count("pk"), converted=Count("pk", filter=Q(has_orders=True))
    )
    deleted = DeletedClientAccount.objects.filter(created_in_period).aggregate(
        total=Count("pk"), converted=Count("pk", filter=Q(had_orders=True))
    )
    return live["total"] + deleted["total"], live["converted"] + deleted["converted"]


def _percentage(part: int, total: int) -> str:
    if not total:
        return "—"
    percent = (Decimal(part) * 100 / total).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return f"{percent}{NBSP}%"
