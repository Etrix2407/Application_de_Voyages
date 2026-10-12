"""Données propres aux tableaux de bord : le journal des exports et les seuils des signaux."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from dashboard.services.periods import DateBasis


class ExportLog(models.Model):
    """Trace de chaque export des commandes : qui, quand, quelle période (RGPD)."""

    exported_at = models.DateTimeField("date", default=timezone.now)
    # Nom figé au moment de l'export : reste lisible si le compte de l'administrateur est supprimé.
    author_name = models.CharField("auteur", max_length=210)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    start = models.DateField("début de la période")
    end = models.DateField("fin de la période")
    basis = models.CharField("base de date", max_length=10, choices=DateBasis.choices)
    row_count = models.PositiveIntegerField("nombre de lignes")

    class Meta:
        verbose_name = "export des commandes"
        verbose_name_plural = "exports des commandes"
        ordering = ["-exported_at", "-pk"]

    def __str__(self) -> str:
        return f"Export du {self.start} au {self.end} — {self.author_name}"


RATE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class SignalThresholds(models.Model):
    """Seuils des signaux du tableau de pilotage, modifiés par l'administrateur (Recap 6).

    Une seule ligne (pk=1), créée avec les valeurs d'origine à la première lecture : voir current().
    Règles d'application : dashboard/services/signals.py.
    """

    max_cancellation_rate = models.PositiveSmallIntegerField(
        "taux d'annulation maximal (%)",
        default=25,
        validators=RATE_VALIDATORS,
        help_text="Un signal s'affiche si le taux d'annulation de la période dépasse ce pourcentage (de 0 à 100).",
    )
    max_overdue_pending = models.PositiveIntegerField(
        "commandes en attente depuis plus de 48 h, au plus",
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Un signal s'affiche s'il y a plus de commandes en attente depuis plus de 48 h que ce nombre.",
    )
    min_processed_within_48h_rate = models.PositiveSmallIntegerField(
        "taux de traitement en 48 h minimal (%)",
        default=80,
        validators=RATE_VALIDATORS,
        help_text="Un signal s'affiche si la part des commandes traitées en 48 h passe sous ce pourcentage "
        "(de 0 à 100).",
    )
    # Vides tant que les seuils d'origine n'ont jamais été modifiés.
    updated_at = models.DateTimeField("modifié le", null=True, blank=True)
    # Nom figé : il reste affiché si le compte de l'administrateur est supprimé ensuite.
    updated_by_name = models.CharField("modifié par", max_length=210, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = "seuils des signaux"
        verbose_name_plural = "seuils des signaux"

    def __str__(self) -> str:
        return "Seuils des signaux"

    @classmethod
    def current(cls) -> "SignalThresholds":
        """Les seuils en vigueur ; la ligne est créée avec les valeurs d'origine si elle n'existe pas."""
        thresholds, _ = cls.objects.get_or_create(pk=1)
        return thresholds
