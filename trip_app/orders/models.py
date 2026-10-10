"""Demandes de voyage : une destination, des dates, des voyageurs et des activités.

Côté client, une commande s'appelle « demande de voyage ». Les prix sont copiés
au moment de la demande : un changement de tarif ultérieur ne la modifie pas.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.models import normalize_email_address
from catalog.models import Activity, Destination
from promotions.models import Promotion

MIN_DAYS_BEFORE_DEPARTURE = 7
MAX_DAYS_BEFORE_DEPARTURE = 2 * 365
MAX_STAY_DAYS = 90
MAX_TRAVELLERS = 10
MAX_REMARKS_LENGTH = 2000
CLIENT_FINGERPRINT_SALT = "orders.Order.client_fingerprint"


def client_fingerprint(email: str) -> str:
    """Empreinte de l'adresse du client, pour la limite d'utilisation d'une promotion par client.

    Adresse normalisée comme pour les comptes, puis sans la partie « +… » (moi+1@x = moi@x).
    HMAC avec la clé secrète du site (SECRET_KEY) : l'adresse n'est pas conservée en clair,
    mais changer cette clé remet les compteurs à zéro.
    """
    local, at, domain = normalize_email_address(email).rpartition("@")
    local = local.split("+", 1)[0]
    return salted_hmac(CLIENT_FINGERPRINT_SALT, f"{local}{at}{domain}", algorithm="sha256").hexdigest()


class Status(models.TextChoices):
    PENDING = "pending", "En attente"
    CONFIRMED = "confirmed", "Confirmée"
    CANCELLED = "cancelled", "Annulée"


def departure_window():
    """Premier et dernier jour de départ possibles pour une nouvelle demande."""
    today = timezone.localdate()
    return today + timedelta(days=MIN_DAYS_BEFORE_DEPARTURE), today + timedelta(days=MAX_DAYS_BEFORE_DEPARTURE)


def _price_field(verbose_name: str, **options) -> models.DecimalField:
    return models.DecimalField(verbose_name, max_digits=10, decimal_places=2, **options)


class Order(models.Model):
    # Vide quand le client a supprimé son compte : la demande est alors anonymisée (RGPD).
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="client",
    )
    # Empreinte de l'adresse e-mail du client (client_fingerprint), remplie à la création,
    # recalculée si le client change d'adresse (orders/signals.py) et conservée après la
    # suppression du compte : la limite « par client » d'une promotion tient malgré une
    # réinscription avec la même adresse. Vide pour les demandes déjà anonymisées avant son ajout.
    client_fingerprint = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
    # PROTECT : une destination déjà demandée ne peut pas être supprimée, seulement désactivée.
    destination = models.ForeignKey(
        Destination, on_delete=models.PROTECT, related_name="orders", verbose_name="destination"
    )
    # Noms figés à la demande, comme les prix : un renommage du catalogue ne la modifie pas.
    destination_name = models.CharField("nom de la destination au moment de la demande", max_length=150)
    country_name = models.CharField("nom du pays au moment de la demande", max_length=100)
    departure_date = models.DateField("date de départ")
    return_date = models.DateField("date de retour")
    adults = models.PositiveSmallIntegerField("adultes", validators=[MinValueValidator(1)])
    children = models.PositiveSmallIntegerField("enfants", default=0)
    # max_length limite le formulaire ; le validateur limite aussi full_clean() (TextField ne le fait pas).
    remarks = models.TextField(
        "remarques", blank=True, max_length=MAX_REMARKS_LENGTH, validators=[MaxLengthValidator(MAX_REMARKS_LENGTH)]
    )
    # Prix figés au moment de la demande. Prix de destination vide = « sur devis ».
    destination_price = _price_field("prix indicatif de la destination", null=True, blank=True)
    estimated_price = _price_field("prix estimé")
    # Recalculé aux tarifs du jour quand le personnel confirme (le prix peut avoir changé
    # depuis la demande). L'estimation de départ reste conservée à côté.
    confirmed_price = _price_field("prix recalculé à la confirmation", null=True, blank=True)
    # Prix de la destination retenu dans ce recalcul (vide = sur devis). Il n'est connu que pour les
    # demandes confirmées après l'ajout de ces champs : le booléen distingue « sur devis » de « inconnu ».
    confirmed_destination_price = _price_field(
        "prix indicatif de la destination à la confirmation", null=True, blank=True
    )
    has_confirmed_destination_price = models.BooleanField(
        "prix de la destination enregistré à la confirmation", default=False
    )
    # Promotion appliquée (v4). Les prix ci-dessus sont après remise. PROTECT : une promotion
    # utilisée ne se supprime pas ; son nom est figé, et ses valeur, portée et assiette ne
    # changent plus une fois utilisée : la remise est ré-appliquée telle quelle à la confirmation.
    promotion = models.ForeignKey(
        Promotion, on_delete=models.PROTECT, null=True, blank=True, related_name="orders", verbose_name="promotion"
    )
    promotion_name = models.CharField("nom de la promotion au moment de la demande", max_length=100, blank=True)
    discount = _price_field("remise à la demande", default=Decimal("0.00"))
    confirmed_discount = _price_field("remise à la confirmation", null=True, blank=True)
    status = models.CharField("état", max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField("date de la demande", default=timezone.now)
    # Jeton de la page de vérification : unique, il empêche qu'un double clic crée deux demandes.
    submission_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)

    class Meta:
        verbose_name = "demande de voyage"
        verbose_name_plural = "demandes de voyage"
        # Le numéro départage les demandes créées au même instant (horloge peu précise).
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return f"Demande n° {self.pk} — {self.destination_name}"

    @property
    def traveller_count(self) -> int:
        return self.adults + self.children

    @property
    def latest_price(self) -> Decimal:
        """Prix le plus récent : celui de la confirmation s'il existe, sinon l'estimation de départ."""
        return self.estimated_price if self.confirmed_price is None else self.confirmed_price

    @property
    def price_before_discount(self) -> Decimal:
        return self.estimated_price + self.discount

    @property
    def confirmed_price_before_discount(self) -> Decimal | None:
        if self.confirmed_price is None:
            return None
        return self.confirmed_price + (self.confirmed_discount or Decimal("0.00"))

    @property
    def confirmed_discount_applies(self) -> bool:
        """La promotion ré-appliquée à la confirmation donne une remise (ex. : 0 € sur un séjour devenu sur devis)."""
        return bool(self.confirmed_discount)

    @property
    def is_quote_required(self) -> bool:
        """La destination n'avait pas de prix indicatif : son prix sera donné sur devis."""
        return self.destination_price is None

    @property
    def is_confirmed_quote_required(self) -> bool:
        """Le prix à la confirmation ne compte pas le séjour : la destination était alors sur devis."""
        return self.has_confirmed_destination_price and self.confirmed_destination_price is None

    @property
    def confirmed_price_includes_stay(self) -> bool:
        return self.has_confirmed_destination_price and self.confirmed_destination_price is not None

    @property
    def is_latest_price_quote_required(self) -> bool:
        """Le prix le plus récent ne compte pas le séjour.

        Demande confirmée avant l'enregistrement du prix de la destination : règle de l'estimation.
        """
        if self.has_confirmed_destination_price:
            return self.is_confirmed_quote_required
        return self.is_quote_required

    @property
    def shows_quote_note_on_estimate(self) -> bool:
        """Mention « sur devis » sous l'estimation, masquée si le prix confirmé compte le séjour."""
        return self.is_quote_required and not self.confirmed_price_includes_stay

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.departure_date and self.return_date and self.return_date <= self.departure_date:
            errors["return_date"] = "La date de retour doit être après la date de départ."
        elif self.departure_date and self.return_date and (self.return_date - self.departure_date).days > MAX_STAY_DAYS:
            errors["return_date"] = f"Un séjour dure au maximum {MAX_STAY_DAYS} jours."
        if self.adults is not None and self.adults < 1:
            errors["adults"] = "Il faut au moins un adulte."
        if (self.adults or 0) + (self.children or 0) > MAX_TRAVELLERS:
            errors["children"] = f"Une demande compte au maximum {MAX_TRAVELLERS} voyageurs."
        # Règles de création : une demande existante reste valable si le temps passe
        # ou si la destination est désactivée ensuite.
        if self._state.adding:
            earliest, latest = departure_window()
            if self.departure_date and self.departure_date < earliest:
                errors["departure_date"] = (
                    f"Le départ doit être au moins {MIN_DAYS_BEFORE_DEPARTURE} jours après la demande."
                )
            elif self.departure_date and self.departure_date > latest:
                errors["departure_date"] = "Le départ doit avoir lieu dans les deux ans."
            if self.destination_id and not Destination.objects.visible().filter(pk=self.destination_id).exists():
                errors["destination"] = "Cette destination n'est plus proposée."
        if errors:
            raise ValidationError(errors)


class OrderActivity(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="activities")
    # PROTECT : une activité déjà demandée ne peut pas être supprimée, seulement désactivée.
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, related_name="order_lines")
    activity_name = models.CharField("nom de l'activité au moment de la demande", max_length=150)
    unit_price = _price_field("prix par personne au moment de la demande")

    class Meta:
        verbose_name = "activité demandée"
        constraints = [
            models.UniqueConstraint(fields=["order", "activity"], name="order_activity_unique")
        ]

    def __str__(self) -> str:
        return self.activity_name

    def clean(self) -> None:
        super().clean()
        if self.activity_id and self.order_id and self.activity.country_id != self.order.destination.country_id:
            raise ValidationError({"activity": "L'activité doit se trouver dans le pays de la destination."})
        # Règle de création : une activité désactivée ensuite reste dans les demandes existantes.
        is_new_line = self._state.adding and self.activity_id
        if is_new_line and not Activity.objects.visible().filter(pk=self.activity_id).exists():
            raise ValidationError({"activity": "Cette activité n'est plus proposée."})


class StatusChange(models.Model):
    """Historique : chaque changement d'état, avec sa date et son auteur."""

    CLIENT_AUTHOR = "Client"
    AGENCY_AUTHOR = "Agence"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField("état", max_length=20, choices=Status.choices)
    changed_at = models.DateTimeField("date", default=timezone.now)
    # Nom figé au moment de l'action : reste lisible si le compte de l'agent est supprimé.
    author_name = models.CharField("auteur", max_length=210)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Texte montré au client dans l'historique : son propre motif, la note de prix recalculé,
    # ou l'explication de l'agence quand elle annule.
    reason = models.TextField("motif visible par le client", blank=True)
    # Annulation par l'agence : motif réservé au personnel, jamais montré au client.
    internal_reason = models.TextField("motif interne", blank=True)
    # Action du client lui-même (sinon : le personnel). Ne dépend pas du libellé affiché.
    by_client = models.BooleanField("par le client", default=False)

    class Meta:
        verbose_name = "changement d'état"
        ordering = ["changed_at", "pk"]

    def __str__(self) -> str:
        return f"{self.get_status_display()} — {self.author_name}"

    @property
    def author_for_client(self) -> str:
        """Auteur montré au client : « Agence » plutôt que le nom de l'agent."""
        return self.CLIENT_AUTHOR if self.by_client else self.AGENCY_AUTHOR
