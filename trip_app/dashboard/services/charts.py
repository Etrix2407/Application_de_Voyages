"""Graphiques du tableau de pilotage : commandes par mois, par pays et par état.

- Les graphiques sont des SVG dessinés côté serveur : ce module calcule les coordonnées
  (entiers, dans le repère du viewBox), le template ne fait que boucler.
- Coordonnées entières : un nombre décimal serait écrit « 12,5 » par la mise en forme française
  du template, ce que le SVG ne comprend pas.
- Pays : celui de la destination (destination__country), et non le nom figé dans la commande
  (country_name) : un pays renommé dans le catalogue reste une seule barre, sous son nom actuel.
"""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, DateField, Q
from django.db.models.functions import TruncMonth

from common.text import NBSP, normalize
from dashboard.services.periods import DateBasis, Period, add_months
from orders.models import Order, OrderStatus

MONTHS_SHOWN = 12
MAX_COUNTRIES = 10
OTHER_COUNTRIES = "Autres pays"
SHORT_MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")

# Repère du viewBox, commun aux graphiques (largeur 100 % à l'écran, texte de 18 unités).
WIDTH = 480

# Courbe : marges pour les libellés de l'axe vertical (à gauche) et des mois (en bas).
LINE_HEIGHT = 260
LINE_LEFT, LINE_RIGHT, LINE_TOP, LINE_BOTTOM = 56, WIDTH - 16, 24, 220

# Barres horizontales : une ligne par barre, le libellé au-dessus, le nombre au bout de la barre.
BAR_ROW = 56
BAR_HEIGHT = 22
BAR_MAX_WIDTH = WIDTH - 120  # place laissée au nombre et au pourcentage (« 1234 (100 %) »)


@dataclass(frozen=True)
class MonthPoint:
    label: str  # « oct. 2026 », pour le tableau et l'infobulle
    count: int
    x: int
    y: int
    # Un mois sur deux, en finissant par le dernier : douze libellés ne tiendraient pas sur un téléphone.
    axis_label: str = ""


@dataclass(frozen=True)
class MonthlyChart:
    points: list[MonthPoint]
    polyline: str  # attribut points de la courbe : « x,y x,y … »
    max_count: int
    first_label: str
    last_label: str
    width: int = WIDTH
    height: int = LINE_HEIGHT
    left: int = LINE_LEFT
    right: int = LINE_RIGHT
    top: int = LINE_TOP
    bottom: int = LINE_BOTTOM


@dataclass(frozen=True)
class Bar:
    label: str
    count: int
    width: int
    label_y: int  # ligne de base du libellé
    bar_y: int  # haut de la barre
    value_x: int  # début du nombre, juste après la barre
    value_y: int
    percent: str = ""  # « 40 % » pour la répartition par état
    css_class: str = ""  # couleur de la barre (le libellé texte dit toujours de quoi il s'agit)


@dataclass(frozen=True)
class BarChart:
    bars: list[Bar]
    height: int
    width: int = WIDTH
    bar_height: int = BAR_HEIGHT


@dataclass(frozen=True)
class OrderCharts:
    monthly: MonthlyChart
    countries: BarChart
    statuses: BarChart


def order_charts(period: Period) -> OrderCharts:
    return OrderCharts(monthly_chart(period), country_chart(period), status_chart(period))


def monthly_chart(period: Period) -> MonthlyChart:
    """Commandes par mois sur les 12 mois civils qui se terminent par le mois de fin de la période."""
    last_month = period.end.replace(day=1)
    months = [add_months(last_month, offset) for offset in range(1 - MONTHS_SHOWN, 1)]
    chart_period = replace(period, start=months[0], end=add_months(last_month, 1) - timedelta(days=1))
    # Date de commande : TruncMonth suit le fuseau courant (Bruxelles), comme les bornes de filter_orders.
    field = "departure_date" if period.basis == DateBasis.DEPARTURE else "created_at"
    rows = (
        chart_period.filter_orders(Order.objects.all())
        .annotate(month=TruncMonth(field, output_field=DateField()))
        .values("month")
        .annotate(count=Count("pk"))
        .order_by()
    )
    counts = {row["month"]: row["count"] for row in rows}

    max_count = max(counts.values(), default=0)
    plot_height = LINE_BOTTOM - LINE_TOP
    step = (LINE_RIGHT - LINE_LEFT) / (MONTHS_SHOWN - 1)
    points = []
    for index, month in enumerate(months):
        count = counts.get(month, 0)
        # Aucune commande sur les 12 mois : la courbe reste à plat sur l'axe, sans division par zéro.
        height = round(count * plot_height / max_count) if max_count else 0
        axis_label = SHORT_MONTHS[month.month - 1] if (MONTHS_SHOWN - 1 - index) % 2 == 0 else ""
        points.append(
            MonthPoint(_month_label(month), count, LINE_LEFT + round(index * step), LINE_BOTTOM - height, axis_label)
        )
    polyline = " ".join(f"{point.x},{point.y}" for point in points)
    return MonthlyChart(points, polyline, max_count, points[0].label, points[-1].label)


def country_chart(period: Period) -> BarChart:
    """Commandes de la période par pays, de la plus demandée à la moins demandée ; au-delà de 10, « Autres pays »."""
    rows = (
        period.filter_orders(Order.objects.all())
        .values("destination__country_id", "destination__country__name")
        .annotate(count=Count("pk"))
        .order_by()
    )
    # Tri en Python (quelques dizaines de pays au plus) : à égalité, ordre alphabétique sans accents.
    ranked = sorted(rows, key=lambda row: (-row["count"], normalize(row["destination__country__name"])))
    entries = [(row["destination__country__name"], row["count"]) for row in ranked[:MAX_COUNTRIES]]
    others = sum(row["count"] for row in ranked[MAX_COUNTRIES:])
    if others:
        entries.append((OTHER_COUNTRIES, others))
    # Barre la plus longue = le plus grand nombre (« Autres pays » compris, il peut dépasser le premier pays).
    largest = max((count for _, count in entries), default=0)
    return _bar_chart([(label, count, largest, "") for label, count in entries], with_percent=False)


def status_chart(period: Period) -> BarChart:
    """Répartition des commandes de la période par état, avec la part de chacun."""
    totals = period.filter_orders(Order.objects.all()).aggregate(
        **{status.value: Count("pk", filter=Q(status=status)) for status in OrderStatus}
    )
    total = sum(totals.values())
    # Barre pleine = toutes les commandes : les longueurs se comparent d'un état à l'autre.
    entries = [(status.label, totals[status.value], total, f"chart-bar-{status.value}") for status in OrderStatus]
    return _bar_chart(entries, with_percent=True)


def _bar_chart(entries: list[tuple[str, int, int, str]], with_percent: bool) -> BarChart:
    """Barres horizontales ; entries : (libellé, nombre, nombre d'une barre pleine, classe CSS)."""
    bars = []
    for index, (label, count, full, css_class) in enumerate(entries):
        top = index * BAR_ROW
        width = round(count * BAR_MAX_WIDTH / full) if full else 0
        if count:
            width = max(width, 2)  # une commande reste visible à côté de mille
        percent = _percent(count, full) if with_percent else ""
        bars.append(Bar(label, count, width, top + 20, top + 28, width + 8, top + 45, percent, css_class))
    return BarChart(bars, height=len(entries) * BAR_ROW)


def _percent(count: int, total: int) -> str:
    """Part arrondie à l'unité (« 33 % ») ; 0 % quand il n'y a aucune commande.

    Les parts arrondies peuvent faire 99 % ou 101 % au total : chacune reste la plus juste possible.
    """
    share = Decimal(count * 100) / total if total else Decimal(0)
    return f"{share.quantize(Decimal('1'), rounding=ROUND_HALF_UP)}{NBSP}%"


def _month_label(month: date) -> str:
    return f"{SHORT_MONTHS[month.month - 1]} {month.year}"
