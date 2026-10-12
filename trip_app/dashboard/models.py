"""Données propres aux tableaux de bord : le journal des exports des commandes."""

from django.conf import settings
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
