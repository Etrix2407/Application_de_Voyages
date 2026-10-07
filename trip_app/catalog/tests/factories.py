"""Création de données de test pour le catalogue."""

from decimal import Decimal

from catalog.models import Activity, Category, Continent, Destination, Difficulty, Country, Visa


def create_country(name="Japon", **fields):
    data = {
        "name": name,
        "continent": Continent.ASIA,
        "main_language": "japonais",
        "currency": "yen",
        "description": "Description du pays.",
        "visa": Visa.NOT_REQUIRED,
        "summer_offset": Decimal("7"),
        "winter_offset": Decimal("8"),
    }
    data.update(fields)
    return Country.objects.create(**data)


def create_destination(country, name="Kyoto", **fields):
    fields.setdefault("description", "Description.")
    return Destination.objects.create(country=country, name=name, **fields)


def create_activity(country, name="Cérémonie du thé", **fields):
    data = {
        "description": "Description.",
        "category": Category.CULTURE,
        "duration_minutes": 90,
        "price_per_person": Decimal("45.00"),
        "difficulty": Difficulty.EASY,
    }
    data.update(fields)
    return Activity.objects.create(country=country, name=name, **data)
