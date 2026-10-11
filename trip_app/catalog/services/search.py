"""Recherche dans le catalogue visible : mot-clé et filtres.

Chaque filtre ne concerne que certains types de résultats. Quand un filtre est
utilisé, les types qu'il ne concerne pas sont écartés : par exemple, filtrer par
catégorie ne montre que des activités.

Tout le filtrage est fait par la base : seuls les résultats sont chargés.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import CharField, F, Q, QuerySet, Value
from django.db.models.functions import Concat

from catalog.models import Activity, Country, Destination
from common.db import Normalize
from common.text import normalize


@dataclass(frozen=True)
class Criteria:
    keyword: str = ""
    continent: str = ""
    category: str = ""
    difficulty: str = ""
    max_budget: Decimal | None = None
    month: int | None = None
    age: int | None = None

    def is_empty(self) -> bool:
        return self == Criteria()


@dataclass
class Results:
    countries: list[Country] = field(default_factory=list)
    destinations: list[Destination] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)

    def total(self) -> int:
        return len(self.countries) + len(self.destinations) + len(self.activities)


def _containing_words(items: QuerySet, words: list[str]) -> QuerySet:
    """Tous les mots figurent dans le nom ou la description, sans tenir compte des accents
    ni des majuscules (fonction SQL Normalize, équivalent de common.text.normalize)."""
    text = Concat("name", Value(" "), "description", output_field=CharField())
    items = items.alias(search_text=Normalize(text))
    for word in words:
        items = items.filter(search_text__contains=word)
    return items


def _ideal_in(month: int) -> Q:
    """Même règle que Destination.ideal_months, la période pouvant chevaucher l'année."""
    within_year = Q(start_month__lte=F("end_month")) & Q(start_month__lte=month, end_month__gte=month)
    over_new_year = Q(start_month__gt=F("end_month")) & (Q(start_month__lte=month) | Q(end_month__gte=month))
    return within_year | over_new_year


def search(criteria: Criteria) -> Results:
    activity_filters = criteria.category or criteria.difficulty or criteria.age is not None
    destination_filter = criteria.month is not None
    price_filter = criteria.max_budget is not None
    words = normalize(criteria.keyword).split()

    results = Results()
    if not (activity_filters or destination_filter or price_filter):
        results.countries = list(_containing_words(_countries(criteria), words))
    if not activity_filters:
        results.destinations = list(_containing_words(_destinations(criteria), words))
    if not destination_filter:
        results.activities = list(_containing_words(_activities(criteria), words))
    return results


def _countries(criteria: Criteria) -> QuerySet:
    countries = Country.objects.visible()
    if criteria.continent:
        countries = countries.filter(continent=criteria.continent)
    return countries


def _destinations(criteria: Criteria) -> QuerySet:
    destinations = Destination.objects.visible().select_related("country")
    if criteria.continent:
        destinations = destinations.filter(country__continent=criteria.continent)
    if criteria.max_budget is not None:
        # Une destination sans prix renseigné n'est pas écartée.
        destinations = destinations.filter(
            Q(price_from__isnull=True) | Q(price_from__lte=criteria.max_budget)
        )
    if criteria.month is not None:
        destinations = destinations.filter(_ideal_in(criteria.month))
    return destinations


def _activities(criteria: Criteria) -> QuerySet:
    activities = Activity.objects.visible().select_related("country", "destination")
    if criteria.continent:
        activities = activities.filter(country__continent=criteria.continent)
    if criteria.category:
        activities = activities.filter(category=criteria.category)
    if criteria.difficulty:
        activities = activities.filter(difficulty=criteria.difficulty)
    if criteria.max_budget is not None:
        activities = activities.filter(price_per_person__lte=criteria.max_budget)
    if criteria.age is not None:
        activities = activities.filter(
            Q(minimum_age__isnull=True) | Q(minimum_age__lte=criteria.age)
        )
    return activities
