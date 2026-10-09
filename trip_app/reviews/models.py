"""Avis des clients sur une destination, après un voyage réellement effectué.

Un avis est lié à une demande de voyage (une seule par avis, un seul avis par demande) :
destination, client et dates du séjour sont lus sur la demande, jamais recopiés.
Seule une demande confirmée par l'agence, dont la date de retour est passée, peut
recevoir un avis : chaque avis publié correspond à un voyage vérifié.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from orders.models import Order

MIN_RATING = 1
MAX_RATING = 5
# Un commentaire est obligatoire pour une note basse, et ces avis sont signalés au personnel.
NEGATIVE_RATING = 2
MAX_TITLE_LENGTH = 100
MAX_COMMENT_LENGTH = 1000
MAX_REFUSAL_DETAILS_LENGTH = 500
# Le client peut modifier ou supprimer son avis pendant ce délai, compté depuis la création.
EDIT_PERIOD = timedelta(days=30)
ANONYMOUS_NAME = "Voyageur anonyme"


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "En attente de validation"
    PUBLISHED = "published", "Publié"
    REFUSED = "refused", "Refusé"


class RefusalReason(models.TextChoices):
    ABUSIVE = "abusive", "Langage injurieux"
    OFF_TOPIC = "off_topic", "Hors sujet"
    PERSONAL_DATA = "personal_data", "Contient des coordonnées personnelles"
    TRIP_CANCELLED = "trip_cancelled", "Voyage annulé"
    OTHER = "other", "Autre"


class ReviewQuerySet(models.QuerySet):
    def public(self):
        """Avis visibles par tous : publiés, sur une destination encore proposée."""
        return self.filter(
            status=ReviewStatus.PUBLISHED,
            order__destination__active=True,
            order__destination__country__active=True,
        )


class Review(models.Model):
    # PROTECT : une demande qui a un avis ne peut pas être supprimée.
    order = models.OneToOneField(
        Order, on_delete=models.PROTECT, related_name="review", verbose_name="demande de voyage"
    )
    rating = models.PositiveSmallIntegerField(
        "note", validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)]
    )
    title = models.CharField("titre", max_length=MAX_TITLE_LENGTH)
    comment = models.TextField(
        "commentaire",
        blank=True,
        max_length=MAX_COMMENT_LENGTH,
        validators=[MaxLengthValidator(MAX_COMMENT_LENGTH)],
    )
    anonymous = models.BooleanField("publier en tant que « Voyageur anonyme »", default=False)
    status = models.CharField("état", max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    refusal_reason = models.CharField("motif du refus", max_length=20, choices=RefusalReason.choices, blank=True)
    refusal_details = models.TextField(
        "précision sur le motif",
        blank=True,
        max_length=MAX_REFUSAL_DETAILS_LENGTH,
        validators=[MaxLengthValidator(MAX_REFUSAL_DETAILS_LENGTH)],
    )
    created_at = models.DateTimeField("date de l'avis", default=timezone.now)
    # Dernier envoi en modération (création ou modification) : ordre de la file du personnel.
    submitted_at = models.DateTimeField("envoyé en validation le", default=timezone.now)
    published_at = models.DateTimeField("date de publication", null=True, blank=True)

    objects = ReviewQuerySet.as_manager()

    class Meta:
        verbose_name = "avis"
        verbose_name_plural = "avis"
        # Le numéro départage les avis créés au même instant (horloge peu précise).
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rating__gte=MIN_RATING, rating__lte=MAX_RATING), name="review_rating_1_to_5"
            ),
        ]

    def __str__(self) -> str:
        return f"Avis {self.rating}/5 — {self.title}"

    @property
    def stars(self) -> str:
        """« ★★★★☆ » : repère visuel, toujours accompagné de la note écrite (« 4 sur 5 »)."""
        return "★" * self.rating + "☆" * (MAX_RATING - self.rating)

    @property
    def is_negative(self) -> bool:
        return self.rating <= NEGATIVE_RATING

    @property
    def editable_until(self):
        return self.created_at + EDIT_PERIOD

    def can_be_changed_by_client(self, now=None) -> bool:
        """Modification ou suppression par le client : 30 jours après la création."""
        return (now or timezone.now()) < self.editable_until

    @property
    def author_name(self) -> str:
        """Nom public : « Julie D. », ou « Voyageur anonyme » (choix du client ou compte supprimé)."""
        client = self.order.client
        if self.anonymous or client is None:
            return ANONYMOUS_NAME
        initial = f" {client.last_name[:1].upper()}." if client.last_name else ""
        return f"{client.first_name}{initial}"

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.rating is not None and self.rating <= NEGATIVE_RATING and not (self.comment or "").strip():
            errors["comment"] = "Un commentaire est obligatoire pour une note de 1 ou 2 étoiles."
        if self.status == ReviewStatus.REFUSED and not self.refusal_reason:
            errors["refusal_reason"] = "Le motif est obligatoire pour refuser ou masquer un avis."
        if self.refusal_reason == RefusalReason.OTHER and not self.refusal_details.strip():
            errors["refusal_details"] = "Précisez le motif quand vous choisissez « Autre »."
        if errors:
            raise ValidationError(errors)
