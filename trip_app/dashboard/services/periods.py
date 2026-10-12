"""Périodes du tableau de pilotage : raccourcis, période personnalisée et période de comparaison.

- Bornes incluses. Une commande compte selon sa date de commande (par défaut) ou sa date de départ.
- Date de commande : jour de Bruxelles (une commande passée à 0 h 30 compte pour ce jour-là).
- Les raccourcis couvrent des mois civils entiers, jours à venir compris (« ce mois-ci » va jusqu'au 31) :
  ils sont comparés aux mêmes mois civils juste avant. Une période personnalisée est comparée
  au même nombre de jours juste avant.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta

from django.db.models import QuerySet, TextChoices
from django.utils import timezone

# Limite d'une période personnalisée : 5 ans (années bissextiles comprises, à un jour près).
MAX_CUSTOM_DAYS = 5 * 366

PREVIOUS_PERIOD = "la période précédente"


class DateBasis(TextChoices):
    ORDERED = "commande", "Date de commande"
    DEPARTURE = "depart", "Date de départ"


class Shortcut(TextChoices):
    THIS_MONTH = "mois", "Ce mois-ci"
    LAST_MONTH = "mois-dernier", "Le mois dernier"
    THIS_QUARTER = "trimestre", "Ce trimestre"
    THIS_YEAR = "annee", "Cette année"
    LAST_12_MONTHS = "12-mois", "Les 12 derniers mois"
    CUSTOM = "personnalisee", "Période personnalisée"


@dataclass(frozen=True)
class Period:
    start: date
    end: date
    basis: str
    # Avec son article : « le mois dernier », pour écrire « par rapport au mois dernier ».
    label: str
    previous_label: str = PREVIOUS_PERIOD
    # Nombre de mois civils couverts ; 0 pour une période personnalisée, comparée jour pour jour.
    months: int = 0

    def filter_orders(self, orders: QuerySet) -> QuerySet:
        if self.basis == DateBasis.DEPARTURE:
            return orders.filter(departure_date__range=(self.start, self.end))
        # Bornes en heure de Bruxelles, fin exclue : l'index sur la date de commande reste utilisable.
        next_day = self.end + timedelta(days=1)
        return orders.filter(created_at__gte=_midnight(self.start), created_at__lt=_midnight(next_day))

    def previous(self) -> "Period":
        if self.months:
            start = _add_months(self.start, -self.months)
        else:
            start = self.start - (self.end - self.start + timedelta(days=1))
        end = self.start - timedelta(days=1)
        return replace(self, start=start, end=end, label=self.previous_label, previous_label=PREVIOUS_PERIOD)

    @property
    def basis_label(self) -> str:
        return DateBasis(self.basis).label

    @property
    def compared_to(self) -> str:
        """« par rapport au mois dernier », « par rapport à l'année dernière »…"""
        label = self.previous_label
        for article, contracted in (("le ", "au "), ("les ", "aux ")):
            if label.startswith(article):
                return f"par rapport {contracted}{label.removeprefix(article)}"
        return f"par rapport à {label}"


# Raccourci : (libellé, libellé de la période précédente, nombre de mois).
_SHORTCUTS = {
    Shortcut.THIS_MONTH: ("ce mois-ci", "le mois dernier", 1),
    Shortcut.LAST_MONTH: ("le mois dernier", "le mois précédent", 1),
    Shortcut.THIS_QUARTER: ("ce trimestre", "le trimestre dernier", 3),
    Shortcut.THIS_YEAR: ("cette année", "l'année dernière", 12),
    Shortcut.LAST_12_MONTHS: ("les 12 derniers mois", "les 12 mois précédents", 12),
}


def shortcut_period(shortcut: str, basis: str = DateBasis.ORDERED, today: date | None = None) -> Period:
    """Période d'un raccourci (tous sauf « personnalisée »), à partir de la date du jour."""
    first_of_month = (today or timezone.localdate()).replace(day=1)
    start = {
        Shortcut.THIS_MONTH: first_of_month,
        Shortcut.LAST_MONTH: _add_months(first_of_month, -1),
        Shortcut.THIS_QUARTER: first_of_month.replace(month=(first_of_month.month - 1) // 3 * 3 + 1),
        Shortcut.THIS_YEAR: first_of_month.replace(month=1),
        # Les 12 mois civils qui se terminent par le mois en cours.
        Shortcut.LAST_12_MONTHS: _add_months(first_of_month, -11),
    }[shortcut]
    label, previous_label, months = _SHORTCUTS[shortcut]
    end = _add_months(start, months) - timedelta(days=1)
    return Period(start, end, basis, label, previous_label, months)


def custom_period(start: date, end: date, basis: str = DateBasis.ORDERED) -> Period:
    return Period(start, end, basis, "la période choisie")


def default_period() -> Period:
    return shortcut_period(Shortcut.THIS_MONTH)


def _add_months(first_of_month: date, months: int) -> date:
    """Premier jour du mois décalé de `months` mois (négatif : en arrière)."""
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _midnight(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))
