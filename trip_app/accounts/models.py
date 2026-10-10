"""Modèle utilisateur : un compte par adresse e-mail, avec un rôle."""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Length
from django.utils import timezone

from .validators import normalize_phone, validate_phone

EMPLOYEE_NUMBER_PREFIX = "AG"
EMPLOYEE_NUMBER_ATTEMPTS = 5


class Role(models.TextChoices):
    CLIENT = "client", "Client"
    AGENT = "agent", "Agent"
    ADMINISTRATOR = "administrator", "Administrateur"


# Agents et administrateur ont les droits d'agent.
STAFF_ROLES = (Role.AGENT, Role.ADMINISTRATOR)


def normalize_email_address(email: str) -> str:
    """Les adresses sont comparées sans tenir compte des majuscules."""
    return email.strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email: str):
        """Permet de se connecter quelle que soit la casse saisie."""
        return self.get(email=normalize_email_address(email))

    def create_user(self, email: str, password: str | None = None, **fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        user = self.model(email=normalize_email_address(email), **fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **fields):
        """Appelée par `manage.py createsuperuser` : crée un compte administrateur."""
        fields.setdefault("role", Role.ADMINISTRATOR)
        if fields["role"] != Role.ADMINISTRATOR:
            raise ValueError("Un superutilisateur doit avoir le rôle administrateur.")
        return self.create_user(email, password, **fields)


# Les droits dépendent uniquement du rôle (voir decorators.py) : pas de permissions Django.
class User(AbstractBaseUser):
    email = models.EmailField("adresse e-mail", unique=True)
    last_name = models.CharField("nom", max_length=100)
    first_name = models.CharField("prénom", max_length=100)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.CLIENT)

    # Données propres aux clients.
    phone = models.CharField(
        "téléphone", max_length=20, blank=True, validators=[validate_phone]
    )
    birth_date = models.DateField("date de naissance", null=True, blank=True)

    # Données propres au personnel (agents et administrateur), attribuées automatiquement.
    employee_number = models.CharField(
        "numéro d'employé", max_length=20, unique=True, null=True, blank=True, editable=False
    )

    is_active = models.BooleanField("actif", default=True)
    date_joined = models.DateTimeField("date d'inscription", default=timezone.now)
    consent_date = models.DateTimeField(
        "date d'acceptation de la politique de confidentialité", null=True, blank=True
    )
    # Inscription client : le compte reste inactif tant que l'adresse n'est pas confirmée.
    email_confirmed_at = models.DateTimeField("date de confirmation de l'adresse", null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["last_name", "first_name"]

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["last_name", "first_name", "pk"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} <{self.email}>"

    @property
    def is_client(self) -> bool:
        return self.role == Role.CLIENT

    @property
    def is_staff_member(self) -> bool:
        return self.role in STAFF_ROLES

    @property
    def is_administrator(self) -> bool:
        return self.role == Role.ADMINISTRATOR

    @property
    def is_awaiting_confirmation(self) -> bool:
        """Inscription client commencée, adresse e-mail pas encore confirmée."""
        return self.is_client and not self.is_active and self.email_confirmed_at is None

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self) -> str:
        return self.first_name

    def clean(self) -> None:
        super().clean()
        self.email = normalize_email_address(self.email)
        if self.phone:
            self.phone = normalize_phone(self.phone)
        if self.is_client:
            self._validate_client_data()

    def _validate_client_data(self) -> None:
        if self.birth_date is None:
            raise ValidationError({"birth_date": "La date de naissance est obligatoire."})
        if self.birth_date >= timezone.localdate():
            raise ValidationError(
                {"birth_date": "La date de naissance doit être dans le passé."}
            )

    def save(self, *args, **kwargs) -> None:
        # Normalisé ici aussi : create_user() et les commandes n'appellent pas clean().
        self.email = normalize_email_address(self.email)
        self.phone = normalize_phone(self.phone)
        if self.is_staff_member and not self.employee_number:
            self._save_with_new_employee_number(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def _save_with_new_employee_number(self, *args, **kwargs) -> None:
        # Deux créations simultanées peuvent calculer le même numéro :
        # on recalcule et on réessaie quelques fois si le numéro vient d'être pris.
        for attempt in range(EMPLOYEE_NUMBER_ATTEMPTS):
            self.employee_number = self._next_employee_number()
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError:
                number_taken = User.objects.filter(employee_number=self.employee_number).exists()
                if not number_taken or attempt == EMPLOYEE_NUMBER_ATTEMPTS - 1:
                    self.employee_number = None
                    raise

    @classmethod
    def _next_employee_number(cls) -> str:
        # Tri par longueur puis par texte : AG10000 passe après AG9999.
        last = (
            cls.objects.filter(employee_number__startswith=EMPLOYEE_NUMBER_PREFIX)
            .order_by(Length("employee_number").desc(), "-employee_number")
            .values_list("employee_number", flat=True)
            .first()
        )
        next_number = int(last.removeprefix(EMPLOYEE_NUMBER_PREFIX)) + 1 if last else 1
        return f"{EMPLOYEE_NUMBER_PREFIX}{next_number:04d}"
