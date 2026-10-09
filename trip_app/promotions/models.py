"""Promotions : remise en pourcentage ou en montant fixe, automatique ou sur code.

Ordre des applications : catalog ← promotions ← orders. Une promotion ne connaît pas
les demandes de voyage ; c'est la demande qui garde la promotion appliquée (v4, feature 3).
"""

import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Country, Destination

MIN_PERCENT = Decimal("1")
MAX_PERCENT = Decimal("50")
CODE_PATTERN = re.compile(r"[A-Z0-9]{4,20}")


class Kind(models.TextChoices):
    PERCENT = "percent", "Pourcentage"
    FIXED = "fixed", "Montant fixe"


class Scope(models.TextChoices):
    CATALOG = "catalog", "Tout le catalogue"
    COUNTRIES = "countries", "Un ou plusieurs pays"
    DESTINATIONS = "destinations", "Une ou plusieurs destinations"


class Base(models.TextChoices):
    """Assiette : la partie du prix sur laquelle porte la remise."""

    STAY = "stay", "Séjour (prix de la destination)"
    ACTIVITIES = "activities", "Activités"
    TOTAL = "total", "Total (séjour + activités)"


class State(models.TextChoices):
    """État affiché, déduit des dates (sauf « Désactivée »)."""

    UPCOMING = "upcoming", "À venir"
    RUNNING = "running", "En cours"
    FINISHED = "finished", "Terminée"
    DISABLED = "disabled", "Désactivée"


class Action(models.TextChoices):
    CREATED = "created", "Création"
    UPDATED = "updated", "Modification"
    DISABLED = "disabled", "Désactivation"


def normalize_code(code: str) -> str:
    """Saisie acceptée en minuscules et avec des espaces autour : « bienvenue15 » → « BIENVENUE15 »."""
    return code.strip().upper()


class PromotionQuerySet(models.QuerySet):
    def running(self, today=None):
        """Promotions actives dont la période de validité contient ce jour (dernier jour inclus)."""
        today = today or timezone.localdate()
        return self.filter(is_active=True, starts_on__lte=today, ends_on__gte=today)

    def automatic(self):
        return self.filter(code__isnull=True)


class Promotion(models.Model):
    name = models.CharField("nom", max_length=100)
    description = models.CharField("description courte", max_length=300, blank=True)
    kind = models.CharField("type", max_length=10, choices=Kind.choices)
    value = models.DecimalField(
        "valeur", max_digits=8, decimal_places=2, help_text="En % pour un pourcentage, en euros pour un montant fixe."
    )
    scope = models.CharField("portée", max_length=15, choices=Scope.choices, default=Scope.CATALOG)
    # Tables intermédiaires en PROTECT : un pays ou une destination visé ne peut pas être supprimé.
    countries = models.ManyToManyField(Country, through="PromotionCountry", blank=True, verbose_name="pays")
    destinations = models.ManyToManyField(
        Destination, through="PromotionDestination", blank=True, verbose_name="destinations"
    )
    base = models.CharField("assiette", max_length=15, choices=Base.choices, default=Base.TOTAL)
    # Validité : date à laquelle le client fait sa demande (pas la date du voyage), dernier jour inclus.
    starts_on = models.DateField("date de début")
    ends_on = models.DateField("date de fin")
    # Facultatif : départs autorisés. Vide = tous les départs.
    departure_from = models.DateField("départs à partir du", null=True, blank=True)
    departure_until = models.DateField("départs jusqu'au", null=True, blank=True)
    # Vide = promotion automatique. Unique, stocké en majuscules.
    code = models.CharField("code promo", max_length=20, null=True, blank=True, unique=True)
    max_uses = models.PositiveIntegerField(
        "maximum de demandes au total", null=True, blank=True, validators=[MinValueValidator(1)]
    )
    max_uses_per_client = models.PositiveIntegerField(
        "maximum par client", null=True, blank=True, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField("active", default=True)
    created_at = models.DateTimeField("créée le", default=timezone.now)

    objects = PromotionQuerySet.as_manager()

    class Meta:
        verbose_name = "promotion"
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        if self.code:
            self.code = normalize_code(self.code)
        errors = {}
        if self.value is not None:
            if self.kind == Kind.PERCENT and not MIN_PERCENT <= self.value <= MAX_PERCENT:
                errors["value"] = f"Un pourcentage est compris entre {MIN_PERCENT} et {MAX_PERCENT} %."
            elif self.kind == Kind.FIXED and self.value <= 0:
                errors["value"] = "Le montant de la remise doit être supérieur à 0 €."
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "La date de fin ne peut pas être avant la date de début."
        if (self.departure_from is None) != (self.departure_until is None):
            errors["departure_until"] = "Indiquez le début et la fin de la période de départ, ou aucun des deux."
        elif self.departure_from and self.departure_until < self.departure_from:
            errors["departure_until"] = "La fin de la période de départ ne peut pas être avant son début."
        if self.code and not CODE_PATTERN.fullmatch(self.code):
            errors["code"] = "Le code compte de 4 à 20 caractères : lettres sans accents et chiffres, sans espaces."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        # Un code vide devient NULL : plusieurs promotions automatiques ne se gênent pas (unicité).
        self.code = normalize_code(self.code) if self.code else None
        super().save(*args, **kwargs)

    @property
    def is_automatic(self) -> bool:
        return not self.code

    @property
    def discount_label(self) -> str:
        """« -15 % », « -12,5 % », « -100 € » ou « -99,50 € »."""
        if self.kind == Kind.PERCENT:
            return f"-{self.value.normalize():f} %".replace(".", ",")
        whole = self.value == self.value.to_integral_value()
        return f"-{self.value:.0f} €" if whole else f"-{self.value:.2f} €".replace(".", ",")

    @property
    def targets_label(self) -> str:
        """« Tout le catalogue » ou la liste des pays / destinations visés (à précharger)."""
        if self.scope == Scope.COUNTRIES:
            return ", ".join(country.name for country in self.countries.all())
        if self.scope == Scope.DESTINATIONS:
            return ", ".join(destination.name for destination in self.destinations.all())
        return Scope.CATALOG.label

    def state(self, today=None) -> State:
        if not self.is_active:
            return State.DISABLED
        today = today or timezone.localdate()
        if today < self.starts_on:
            return State.UPCOMING
        if today > self.ends_on:
            return State.FINISHED
        return State.RUNNING

    @property
    def created_by_name(self) -> str:
        """Auteur de la création, lu dans l'historique (nom figé)."""
        creation = self.history.filter(action=Action.CREATED).first()
        return creation.author_name if creation else ""


def targets_problem(scope: str, countries, destinations) -> dict[str, str]:
    """Erreurs de portée, par champ ; vide si la portée est valable.

    Les pays et destinations sont liés après l'enregistrement : le formulaire vérifie
    cette règle avant d'enregistrer (Promotion.clean ne voit pas encore les liens).
    """
    if scope == Scope.COUNTRIES and not countries:
        return {"countries": "Choisissez au moins un pays."}
    if scope == Scope.DESTINATIONS and not destinations:
        return {"destinations": "Choisissez au moins une destination."}
    return {}


class PromotionCountry(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["promotion", "country"], name="promotion_country_unique")]


class PromotionDestination(models.Model):
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE)
    destination = models.ForeignKey(Destination, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["promotion", "destination"], name="promotion_destination_unique")
        ]


class PromotionChange(models.Model):
    """Historique : création, modifications et désactivation, avec leur date et leur auteur."""

    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="history")
    action = models.CharField("action", max_length=10, choices=Action.choices)
    changed_at = models.DateTimeField("date", default=timezone.now)
    # Nom figé au moment de l'action : reste lisible si le compte de l'administrateur est supprimé.
    author_name = models.CharField("auteur", max_length=210)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    details = models.TextField("détails", blank=True)

    class Meta:
        verbose_name = "changement de promotion"
        ordering = ["changed_at", "pk"]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.author_name}"
