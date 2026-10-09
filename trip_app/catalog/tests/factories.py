"""Création de données de test pour le catalogue."""

import io
import shutil
from decimal import Decimal

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from catalog.models import Activity, Category, Continent, Destination, Difficulty, Country, Visa


def create_country(name="Japon", **fields):
    data = {
        "name": name,
        "continent": Continent.ASIA,
        "main_language": "japonais",
        "currency": "yen",
        "description": "Description du pays.",
        "visa": Visa.NOT_REQUIRED,
        "time_zone": "Asia/Tokyo",
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


def make_image(name: str = "photo.png", image_format: str = "PNG") -> SimpleUploadedFile:
    """Petite image valide générée en mémoire, au format demandé."""
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f"image/{image_format.lower()}")


TEST_MEDIA_ROOT = settings.BASE_DIR / "_test_media"


class TemporaryMediaMixin:
    """Les photos envoyées pendant un test vont dans un dossier vidé après chaque test."""

    def setUp(self):
        super().setUp()
        media = override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
        media.enable()
        self.addCleanup(media.disable)
        self.addCleanup(shutil.rmtree, TEST_MEDIA_ROOT, True)
