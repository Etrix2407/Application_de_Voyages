"""Catalogue : pays, destinations et activités."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models, transaction

from common.text import normalize

from .validators import PHOTO_EXTENSIONS, validate_photo_size, validate_time_offset


def format_offset(hours: Decimal) -> str:
    """Affiche un décalage horaire lisible : « +5 h 30 », « -6 h », « même heure »."""
    if not hours:
        return "même heure qu'en Belgique"
    sign = "+" if hours > 0 else "-"
    total_minutes = int(abs(hours) * 60)
    h, minutes = divmod(total_minutes, 60)
    return f"{sign}{h} h {minutes:02d}" if minutes else f"{sign}{h} h"


class Continent(models.TextChoices):
    AFRICA = "africa", "Afrique"
    AMERICA = "america", "Amérique"
    ASIA = "asia", "Asie"
    EUROPE = "europe", "Europe"
    OCEANIA = "oceania", "Océanie"


class Visa(models.TextChoices):
    NOT_REQUIRED = "not_required", "Non requis"
    E_VISA = "e_visa", "Visa électronique (e-visa)"
    ON_ARRIVAL = "on_arrival", "Visa à l'arrivée"
    BEFORE_DEPARTURE = "before_departure", "Visa à demander avant le départ"


class Month(models.IntegerChoices):
    JANUARY = 1, "janvier"
    FEBRUARY = 2, "février"
    MARCH = 3, "mars"
    APRIL = 4, "avril"
    MAY = 5, "mai"
    JUNE = 6, "juin"
    JULY = 7, "juillet"
    AUGUST = 8, "août"
    SEPTEMBER = 9, "septembre"
    OCTOBER = 10, "octobre"
    NOVEMBER = 11, "novembre"
    DECEMBER = 12, "décembre"


class Category(models.TextChoices):
    CULTURE = "culture", "Culture"
    RELAXATION = "relaxation", "Détente"
    SPORT = "sport", "Sport"
    GASTRONOMY = "gastronomy", "Gastronomie"
    ADVENTURE = "adventure", "Aventure"


class Difficulty(models.TextChoices):
    EASY = "easy", "Facile"
    MEDIUM = "medium", "Moyen"
    HARD = "hard", "Difficile"


def _price_field(verbose_name: str, **options) -> models.DecimalField:
    return models.DecimalField(
        verbose_name,
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="En euros.",
        **options,
    )


def _offset_field(verbose_name: str) -> models.DecimalField:
    return models.DecimalField(
        verbose_name,
        max_digits=4,
        decimal_places=2,
        validators=[validate_time_offset],
        help_text="En heures par rapport à la Belgique, par exemple 5.5 ou -6.",
    )


# Visibilité pour les clients (règle 5 : un pays désactivé disparaît avec son contenu).


class CountryQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(active=True)


class DestinationQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(active=True, country__active=True)


class ActivityQuerySet(models.QuerySet):
    def visible(self):
        return self.filter(active=True, country__active=True).exclude(destination__active=False)


class Country(models.Model):
    name = models.CharField("nom", max_length=100)
    continent = models.CharField(max_length=20, choices=Continent.choices)
    main_language = models.CharField("langue principale", max_length=100)
    currency = models.CharField("monnaie", max_length=100)
    description = models.TextField()
    visa = models.CharField(
        "visa pour les Belges", max_length=20, choices=Visa.choices, default=Visa.NOT_REQUIRED
    )
    summer_offset = _offset_field("décalage horaire en été")
    winter_offset = _offset_field("décalage horaire en hiver")
    active = models.BooleanField("actif", default=True)
    # Nom normalisé (sans accents ni majuscules) : « Perou » et « PÉROU » sont des doublons.
    name_key = models.CharField(max_length=100, unique=True, editable=False)

    objects = CountryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "pays"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        duplicates = Country.objects.filter(name_key=normalize(self.name)).exclude(pk=self.pk)
        if self.name and duplicates.exists():
            raise ValidationError({"name": "Un pays avec ce nom existe déjà."})

    def save(self, *args, **kwargs) -> None:
        self.name_key = normalize(self.name)
        super().save(*args, **kwargs)

    def summer_offset_display(self) -> str:
        return format_offset(self.summer_offset)

    def winter_offset_display(self) -> str:
        return format_offset(self.winter_offset)

    def can_be_deleted(self) -> bool:
        """Règle 5 : un pays qui contient des destinations ou des activités se désactive."""
        return not (self.destinations.exists() or self.activities.exists())


def _delete_file_after_commit(storage, name: str) -> None:
    """Supprime le fichier seulement si l'enregistrement en base a réussi."""
    transaction.on_commit(lambda: storage.delete(name))


def _photo_path(instance, filename: str) -> str:
    """Nom de fichier aléatoire : le nom d'origine (parfois personnel) n'est jamais publié."""
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"destinations/{uuid.uuid4().hex}.{extension}"


class Destination(models.Model):
    name = models.CharField("nom", max_length=150)
    description = models.TextField()
    start_month = models.PositiveSmallIntegerField(
        "période idéale : de", choices=Month.choices, null=True, blank=True
    )
    end_month = models.PositiveSmallIntegerField(
        "période idéale : à", choices=Month.choices, null=True, blank=True
    )
    price_from = _price_field("prix indicatif « à partir de »", null=True, blank=True)
    photo = models.ImageField(
        "photo",
        upload_to=_photo_path,
        blank=True,
        validators=[
            FileExtensionValidator(
                PHOTO_EXTENSIONS, message="Formats acceptés : JPEG, PNG ou WebP."
            ),
            validate_photo_size,
        ],
        help_text="Facultatif. JPEG, PNG ou WebP, 5 Mo maximum.",
    )
    # Règle 3 : une destination appartient à un seul pays ; PROTECT applique la règle 5.
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name="pays", related_name="destinations"
    )
    active = models.BooleanField("actif", default=True)

    objects = DestinationQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if (self.start_month is None) != (self.end_month is None):
            raise ValidationError(
                "Indiquez le mois de début et le mois de fin de la période idéale, ou aucun des deux."
            )

    def save(self, *args, **kwargs) -> None:
        old_photo = ""
        if self.pk:
            old_photo = Destination.objects.filter(pk=self.pk).values_list("photo", flat=True).first() or ""
        super().save(*args, **kwargs)
        if old_photo and old_photo != self.photo.name:
            _delete_file_after_commit(self.photo.storage, old_photo)

    def delete(self, *args, **kwargs):
        photo = self.photo
        result = super().delete(*args, **kwargs)
        if photo:
            _delete_file_after_commit(photo.storage, photo.name)
        return result

    def ideal_months(self) -> list[int]:
        """Mois de la période idéale ; elle peut chevaucher l'année (novembre à mars)."""
        if self.start_month is None or self.end_month is None:
            return []
        count = (self.end_month - self.start_month) % 12 + 1
        return [(self.start_month - 1 + i) % 12 + 1 for i in range(count)]

    def ideal_period(self) -> str:
        months = self.ideal_months()
        if not months:
            return ""
        if len(months) == 12:
            return "toute l'année"
        if len(months) == 1:
            return Month(months[0]).label
        start = Month(self.start_month).label
        prefix = "d'" if start[0] in "aeiou" else "de "
        return f"{prefix}{start} à {Month(self.end_month).label}"


class Activity(models.Model):
    name = models.CharField("nom", max_length=150)
    description = models.TextField()
    category = models.CharField("catégorie", max_length=20, choices=Category.choices)
    duration_minutes = models.PositiveIntegerField(
        "durée (en minutes)", validators=[MinValueValidator(1)]
    )
    price_per_person = _price_field("prix par personne")
    difficulty = models.CharField("niveau de difficulté", max_length=20, choices=Difficulty.choices)
    minimum_age = models.PositiveSmallIntegerField(
        "âge minimum",
        null=True,
        blank=True,
        validators=[MaxValueValidator(99)],
        help_text="Laisser vide si l'activité convient à tous les âges.",
    )
    # Règle 4 : une activité est proposée dans un seul pays, destination précise optionnelle.
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, verbose_name="pays", related_name="activities"
    )
    destination = models.ForeignKey(
        Destination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activities",
    )
    active = models.BooleanField("actif", default=True)

    objects = ActivityQuerySet.as_manager()

    class Meta:
        verbose_name = "activité"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.destination_id and self.country_id and self.destination.country_id != self.country_id:
            raise ValidationError(
                {"destination": "La destination doit se trouver dans le pays de l'activité."}
            )

    def duration_display(self) -> str:
        hours, minutes = divmod(self.duration_minutes, 60)
        if not hours:
            return f"{minutes} min"
        return f"{hours} h {minutes:02d}" if minutes else f"{hours} h"


# Favoris des clients (suppression en cascade avec le compte : droit à l'effacement).


class Favorite(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    added_at = models.DateTimeField("date d'ajout", auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-added_at"]


class FavoriteDestination(Favorite):
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)

    class Meta(Favorite.Meta):
        verbose_name = "destination favorite"
        constraints = [
            models.UniqueConstraint(fields=["client", "destination"], name="favorite_destination_unique")
        ]


class FavoriteActivity(Favorite):
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, verbose_name="activité")

    class Meta(Favorite.Meta):
        verbose_name = "activité favorite"
        constraints = [
            models.UniqueConstraint(fields=["client", "activity"], name="favorite_activity_unique")
        ]
