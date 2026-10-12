"""Section « commandes » du tableau de pilotage : nombres par état, montants estimés, délai de traitement.

- Toutes les commandes de la période comptent (Period.filter_orders), chaque chiffre est comparé
  à la période précédente.
- Montants : montant estimé et remise les plus récents (dashboard.services.order_figures), après remise.
  Ce n'est pas de l'argent encaissé.
- Total des remises : commandes non annulées seulement, comme les statistiques d'une promotion.
- Taux : en pourcentage (Decimal, 0 à 100) des commandes de la période ; aucune commande → None (tiret).
- Délai de traitement : de la création de la commande à la première confirmation ou annulation
  par le personnel (StatusChange.by_client=False). Une annulation par le client n'est pas un traitement
  de l'agence : une commande annulée par le client sans décision du personnel est exclue du délai.
  Une commande encore en attente n'a pas de délai : elle compte dans overdue_pending_count.
- 48 heures réelles, week-end compris (OVERDUE_DELAY). « En moins de 48 h » : 48 h pile comprises,
  comme une commande n'est en retard qu'au-delà de 48 h.

Signaux (lus par une autre section) :
- cancellation_rate : taux d'annulation de la période, en pourcentage (Decimal), None sans commande ;
- processed_within_48h_rate : part des commandes traitées (décision du personnel) en 48 h au plus,
  en pourcentage (Decimal), None si aucune commande traitée ;
- overdue_pending_count : commandes en attente depuis plus de 48 h à l'instant du calcul,
  toutes périodes confondues (le tableau étant en cache, le chiffre peut dater d'une heure).
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from common.text import NBSP, euros
from dashboard.services.comparison import NEUTRAL, Comparison, compare
from dashboard.services.order_figures import OVERDUE_DELAY, latest_discount, latest_price
from dashboard.services.periods import Period
from orders.models import Order, OrderStatus, StatusChange

DASH = "—"
_ZERO = Decimal("0.00")


@dataclass(frozen=True)
class OrderFigures:
    """Chiffres bruts d'une période (servent aussi à la comparaison)."""

    pending_count: int
    confirmed_count: int
    cancelled_count: int
    total_count: int
    confirmed_amount: Decimal
    cancelled_amount: Decimal
    pending_amount: Decimal
    total_discount: Decimal
    confirmation_rate: Decimal | None
    cancellation_rate: Decimal | None
    average_delay: timedelta | None
    longest_delay: timedelta | None
    processed_within_48h_rate: Decimal | None


@dataclass(frozen=True)
class KeyFigure:
    """Gros chiffre prêt à afficher (partiel dashboard/_figure.html)."""

    label: str
    value: str
    comparison: Comparison


@dataclass(frozen=True)
class OrdersSection:
    counts: list[KeyFigure]
    amounts: list[KeyFigure]
    cancelled_amount: KeyFigure
    delays: list[KeyFigure]
    # Signaux : voir la docstring du module.
    cancellation_rate: Decimal | None
    processed_within_48h_rate: Decimal | None
    overdue_pending_count: int


def orders_section(period: Period) -> OrdersSection:
    current = order_figures(period)
    previous = order_figures(period.previous())

    def figure(label: str, attribute: str, show, higher_is_better: bool = True) -> KeyFigure:
        value = getattr(current, attribute)
        comparison = _compare(value, getattr(previous, attribute), higher_is_better)
        return KeyFigure(label, DASH if value is None else show(value), comparison)

    # Sens retenus : plus de commandes (même en attente) = plus de demande, c'est bien ;
    # plus de remises = moins de recettes, c'est mauvais ; un délai plus long est mauvais.
    return OrdersSection(
        counts=[
            figure("Commandes en attente", "pending_count", str),
            figure("Commandes confirmées", "confirmed_count", str),
            figure("Commandes annulées", "cancelled_count", str, higher_is_better=False),
            figure("Total des commandes", "total_count", str),
            figure("Taux de confirmation", "confirmation_rate", _percent_text),
            figure("Taux d'annulation", "cancellation_rate", _percent_text, higher_is_better=False),
        ],
        amounts=[
            figure("Montant estimé des commandes confirmées", "confirmed_amount", euros),
            figure("Potentiel en attente", "pending_amount", euros),
            figure("Total des remises accordées", "total_discount", euros, higher_is_better=False),
        ],
        cancelled_amount=figure(
            "Montant estimé des commandes annulées", "cancelled_amount", euros, higher_is_better=False
        ),
        delays=[
            figure("Délai moyen de traitement", "average_delay", _delay_text, higher_is_better=False),
            figure("Délai le plus long", "longest_delay", _delay_text, higher_is_better=False),
            figure("Commandes traitées en moins de 48 h", "processed_within_48h_rate", _percent_text),
        ],
        cancellation_rate=current.cancellation_rate,
        processed_within_48h_rate=current.processed_within_48h_rate,
        overdue_pending_count=Order.objects.filter(
            status=OrderStatus.PENDING, created_at__lt=timezone.now() - OVERDUE_DELAY
        ).count(),
    )


def order_figures(period: Period) -> OrderFigures:
    orders = period.filter_orders(Order.objects.all())
    pending = Q(status=OrderStatus.PENDING)
    confirmed = Q(status=OrderStatus.CONFIRMED)
    cancelled = Q(status=OrderStatus.CANCELLED)
    figures = orders.aggregate(
        pending_count=Count("pk", filter=pending),
        confirmed_count=Count("pk", filter=confirmed),
        cancelled_count=Count("pk", filter=cancelled),
        total_count=Count("pk"),
        confirmed_amount=Coalesce(Sum(latest_price(), filter=confirmed), _ZERO),
        cancelled_amount=Coalesce(Sum(latest_price(), filter=cancelled), _ZERO),
        pending_amount=Coalesce(Sum(latest_price(), filter=pending), _ZERO),
        total_discount=Coalesce(Sum(latest_discount(), filter=~cancelled), _ZERO),
    )
    delays = _processing_delays(orders)
    total = figures["total_count"]
    return OrderFigures(
        **figures,
        confirmation_rate=_rate(figures["confirmed_count"], total),
        cancellation_rate=_rate(figures["cancelled_count"], total),
        average_delay=sum(delays, timedelta()) / len(delays) if delays else None,
        longest_delay=max(delays, default=None),
        processed_within_48h_rate=_rate(sum(delay <= OVERDUE_DELAY for delay in delays), len(delays)),
    )


def _processing_delays(orders) -> list[timedelta]:
    """Délai de chaque commande traitée par le personnel, en une seule requête.

    La différence de dates est calculée en Python : SQLite ne sait pas soustraire deux dates.
    """
    first_decision = (
        StatusChange.objects.filter(
            order=OuterRef("pk"), by_client=False, status__in=[OrderStatus.CONFIRMED, OrderStatus.CANCELLED]
        )
        .order_by("changed_at", "pk")
        .values("changed_at")[:1]
    )
    pairs = (
        orders.annotate(first_decision=Subquery(first_decision))
        .filter(first_decision__isnull=False)
        .values_list("created_at", "first_decision")
    )
    return [decided_at - created_at for created_at, decided_at in pairs]


def _rate(part: int, total: int) -> Decimal | None:
    """Pourcentage arrondi au dixième ; None quand il n'y a rien à compter (jamais de division par zéro)."""
    if not total:
        return None
    return (Decimal(part) * 100 / total).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _compare(current, previous, higher_is_better: bool) -> Comparison:
    """Comme compare(), mais un taux ou un délai absent d'un côté ne se compare pas : un tiret."""
    if current is None or previous is None:
        return Comparison(DASH, NEUTRAL)
    if isinstance(current, timedelta):
        current, previous = current.total_seconds(), previous.total_seconds()
    return compare(current, previous, higher_is_better)


def _percent_text(rate: Decimal) -> str:
    """« 87 % », arrondi à l'unité."""
    return f"{rate.quantize(Decimal('1'), rounding=ROUND_HALF_UP)}{NBSP}%"


def _delay_text(delay: timedelta) -> str:
    """« 45 min », « 5 h », « 1 j 4 h » ; tronqué (47 h 59 reste sous les 48 h)."""
    minutes = int(delay.total_seconds()) // 60
    if minutes < 60:
        return f"{minutes}{NBSP}min"
    days, hours = divmod(minutes // 60, 24)
    if not days:
        return f"{hours}{NBSP}h"
    return f"{days}{NBSP}j {hours}{NBSP}h" if hours else f"{days}{NBSP}j"
