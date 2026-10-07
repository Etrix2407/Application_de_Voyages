"""Modèle utilisateur : un compte par adresse e-mail, avec un rôle."""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .validators import normaliser_telephone, valider_telephone_belge

PREFIXE_NUMERO_EMPLOYE = "AG"


class Role(models.TextChoices):
    CLIENT = "client", "Client"
    AGENT = "agent", "Agent"
    ADMINISTRATEUR = "administrateur", "Administrateur"


def normaliser_email(email: str) -> str:
    """Les adresses sont comparées sans tenir compte des majuscules."""
    return email.strip().lower()


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email: str):
        """Permet de se connecter quelle que soit la casse saisie."""
        return self.get(email=normaliser_email(email))

    def create_user(self, email: str, password: str | None = None, **champs):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        utilisateur = self.model(email=normaliser_email(email), **champs)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_superuser(self, email: str, password: str | None = None, **champs):
        champs.setdefault("role", Role.ADMINISTRATEUR)
        champs.setdefault("is_staff", True)
        champs.setdefault("is_superuser", True)
        if champs["role"] != Role.ADMINISTRATEUR:
            raise ValueError("Un superutilisateur doit avoir le rôle administrateur.")
        return self.create_user(email, password, **champs)


class Utilisateur(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("adresse e-mail", unique=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField("prénom", max_length=100)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.CLIENT)

    # Données propres aux clients.
    telephone = models.CharField(
        "téléphone", max_length=20, blank=True, validators=[valider_telephone_belge]
    )
    date_naissance = models.DateField("date de naissance", null=True, blank=True)

    # Données propres au personnel (agents et administrateur), attribuées automatiquement.
    numero_employe = models.CharField(
        "numéro d'employé", max_length=20, unique=True, null=True, blank=True, editable=False
    )

    is_active = models.BooleanField("actif", default=True)
    is_staff = models.BooleanField("accès à l'administration Django", default=False)
    date_inscription = models.DateTimeField("date d'inscription", default=timezone.now)
    date_consentement = models.DateTimeField(
        "date d'acceptation de la politique de confidentialité", null=True, blank=True
    )

    objects = UtilisateurManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nom", "prenom"]

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["nom", "prenom"]

    def __str__(self) -> str:
        return f"{self.prenom} {self.nom} <{self.email}>"

    @property
    def est_client(self) -> bool:
        return self.role == Role.CLIENT

    @property
    def est_personnel(self) -> bool:
        """Agents et administrateur ont les droits d'agent."""
        return self.role in (Role.AGENT, Role.ADMINISTRATEUR)

    @property
    def est_administrateur(self) -> bool:
        return self.role == Role.ADMINISTRATEUR

    def get_full_name(self) -> str:
        return f"{self.prenom} {self.nom}"

    def get_short_name(self) -> str:
        return self.prenom

    def clean(self) -> None:
        super().clean()
        self.email = normaliser_email(self.email)
        if self.telephone:
            self.telephone = normaliser_telephone(self.telephone)
        if self.est_client:
            self._valider_donnees_client()

    def _valider_donnees_client(self) -> None:
        if self.date_naissance is None:
            raise ValidationError({"date_naissance": "La date de naissance est obligatoire."})
        if self.date_naissance >= timezone.localdate():
            raise ValidationError(
                {"date_naissance": "La date de naissance doit être dans le passé."}
            )

    def save(self, *args, **kwargs) -> None:
        self.email = normaliser_email(self.email)
        if self.est_personnel and not self.numero_employe:
            self.numero_employe = self._prochain_numero_employe()
        super().save(*args, **kwargs)

    @classmethod
    def _prochain_numero_employe(cls) -> str:
        dernier = (
            cls.objects.filter(numero_employe__startswith=PREFIXE_NUMERO_EMPLOYE)
            .order_by("-numero_employe")
            .values_list("numero_employe", flat=True)
            .first()
        )
        suivant = int(dernier.removeprefix(PREFIXE_NUMERO_EMPLOYE)) + 1 if dernier else 1
        return f"{PREFIXE_NUMERO_EMPLOYE}{suivant:04d}"
