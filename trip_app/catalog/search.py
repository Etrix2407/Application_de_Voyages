"""Recherche dans le catalogue visible : mot-clé et filtres.

Chaque filtre ne concerne que certains types de résultats. Quand un filtre est
utilisé, les types qu'il ne concerne pas sont écartés : par exemple, filtrer par
catégorie ne montre que des activités.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q

from config.text import normalize

from .models import Activity, Destination, Country


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


def _contains_words(item, words: list[str]) -> bool:
    text = normalize(f"{item.name} {item.description}")
    return all(keyword in text for keyword in words)


def search(criteria: Criteria) -> Results:
    activity_filters = criteria.category or criteria.difficulty or criteria.age is not None
    destination_filter = criteria.month is not None
    price_filter = criteria.max_budget is not None

    results = Results()
    if not (activity_filters or destination_filter or price_filter):
        results.countries = list(_countries(criteria))
    if not activity_filters:
        results.destinations = list(_destinations(criteria))
    if not destination_filter:
        results.activities = list(_activities(criteria))

    # Recherche par mot en Python : SQLite ne sait pas ignorer les accents.
    words = normalize(criteria.keyword).split()
    if words:
        results.countries = [p for p in results.countries if _contains_words(p, words)]
        results.destinations = [
            d for d in results.destinations if _contains_words(d, words)
        ]
        results.activities = [a for a in results.activities if _contains_words(a, words)]
    return results


def _countries(criteria: Criteria):
    countries = Country.objects.visible()
    if criteria.continent:
        countries = countries.filter(continent=criteria.continent)
    return countries


def _destinations(criteria: Criteria):
    destinations = Destination.objects.visible().select_related("country")
    if criteria.continent:
        destinations = destinations.filter(country__continent=criteria.continent)
    if criteria.max_budget is not None:
        # Une destination sans prix renseigné n'est pas écartée.
        destinations = destinations.filter(
            Q(price_from__isnull=True) | Q(price_from__lte=criteria.max_budget)
        )
    if criteria.month is not None:
        return [d for d in destinations if criteria.month in d.ideal_months()]
    return destinations


def _activities(criteria: Criteria):
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
