"""Catalogue : pays, destinations et activités."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .validators import valider_decalage_horaire


def afficher_decalage(heures: Decimal) -> str:
    """Affiche un décalage horaire lisible : « +5 h 30 », « -6 h », « même heure »."""
    if not heures:
        return "même heure qu'en Belgique"
    signe = "+" if heures > 0 else "-"
    total_minutes = int(abs(heures) * 60)
    h, minutes = divmod(total_minutes, 60)
    return f"{signe}{h} h {minutes:02d}" if minutes else f"{signe}{h} h"


def cle_de_nom(nom: str) -> str:
    """Compare les noms sans tenir compte des majuscules ni des espaces autour."""
    return nom.strip().casefold()


class Continent(models.TextChoices):
    AFRIQUE = "afrique", "Afrique"
    AMERIQUE = "amerique", "Amérique"
    ASIE = "asie", "Asie"
    EUROPE = "europe", "Europe"
    OCEANIE = "oceanie", "Océanie"


class Visa(models.TextChoices):
    NON_REQUIS = "non_requis", "Non requis"
    E_VISA = "e_visa", "Visa électronique (e-visa)"
    A_L_ARRIVEE = "a_l_arrivee", "Visa à l'arrivée"
    AVANT_DEPART = "avant_depart", "Visa à demander avant le départ"


class Mois(models.IntegerChoices):
    JANVIER = 1, "janvier"
    FEVRIER = 2, "février"
    MARS = 3, "mars"
    AVRIL = 4, "avril"
    MAI = 5, "mai"
    JUIN = 6, "juin"
    JUILLET = 7, "juillet"
    AOUT = 8, "août"
    SEPTEMBRE = 9, "septembre"
    OCTOBRE = 10, "octobre"
    NOVEMBRE = 11, "novembre"
    DECEMBRE = 12, "décembre"


class Categorie(models.TextChoices):
    CULTURE = "culture", "Culture"
    DETENTE = "detente", "Détente"
    SPORT = "sport", "Sport"
    GASTRONOMIE = "gastronomie", "Gastronomie"
    AVENTURE = "aventure", "Aventure"


class Difficulte(models.TextChoices):
    FACILE = "facile", "Facile"
    MOYEN = "moyen", "Moyen"
    DIFFICILE = "difficile", "Difficile"


def _champ_prix(verbose_name: str, **options) -> models.DecimalField:
    return models.DecimalField(
        verbose_name,
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="En euros.",
        **options,
    )


def _champ_decalage(verbose_name: str) -> models.DecimalField:
    return models.DecimalField(
        verbose_name,
        max_digits=4,
        decimal_places=2,
        validators=[valider_decalage_horaire],
        help_text="En heures par rapport à la Belgique, par exemple 5.5 ou -6.",
    )


# Visibilité pour les clients (règle 5 : un pays désactivé disparaît avec son contenu).


class PaysQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(actif=True)


class DestinationQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(actif=True, pays__actif=True)


class ActiviteQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(actif=True, pays__actif=True).exclude(destination__actif=False)


class Pays(models.Model):
    nom = models.CharField(max_length=100)
    continent = models.CharField(max_length=20, choices=Continent.choices)
    langue_principale = models.CharField("langue principale", max_length=100)
    monnaie = models.CharField(max_length=100)
    description = models.TextField()
    visa = models.CharField(
        "visa pour les Belges", max_length=20, choices=Visa.choices, default=Visa.NON_REQUIS
    )
    decalage_ete = _champ_decalage("décalage horaire en été")
    decalage_hiver = _champ_decalage("décalage horaire en hiver")
    actif = models.BooleanField(default=True)
    # Nom normalisé (sans majuscules) garantissant l'unicité, y compris pour les accents.
    nom_cle = models.CharField(max_length=100, unique=True, editable=False)

    objects = PaysQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "pays"
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom

    def clean(self) -> None:
        super().clean()
        doublons = Pays.objects.filter(nom_cle=cle_de_nom(self.nom)).exclude(pk=self.pk)
        if self.nom and doublons.exists():
            raise ValidationError({"nom": "Un pays avec ce nom existe déjà."})

    def save(self, *args, **kwargs) -> None:
        self.nom_cle = cle_de_nom(self.nom)
        super().save(*args, **kwargs)

    def decalage_ete_affiche(self) -> str:
        return afficher_decalage(self.decalage_ete)

    def decalage_hiver_affiche(self) -> str:
        return afficher_decalage(self.decalage_hiver)

    def peut_etre_supprime(self) -> bool:
        """Règle 5 : un pays qui contient des destinations ou des activités se désactive."""
        return not (self.destinations.exists() or self.activites.exists())


class Destination(models.Model):
    nom = models.CharField(max_length=150)
    description = models.TextField()
    mois_debut = models.PositiveSmallIntegerField(
        "période idéale : de", choices=Mois.choices, null=True, blank=True
    )
    mois_fin = models.PositiveSmallIntegerField(
        "période idéale : à", choices=Mois.choices, null=True, blank=True
    )
    prix_a_partir_de = _champ_prix("prix indicatif « à partir de »", null=True, blank=True)
    photo = models.URLField("adresse (URL) de la photo", blank=True)
    # Règle 3 : une destination appartient à un seul pays ; PROTECT applique la règle 5.
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="destinations")
    actif = models.BooleanField(default=True)

    objects = DestinationQuerySet.as_manager()

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom

    def clean(self) -> None:
        super().clean()
        if (self.mois_debut is None) != (self.mois_fin is None):
            raise ValidationError(
                "Indiquez le mois de début et le mois de fin de la période idéale, ou aucun des deux."
            )

    def mois_ideaux(self) -> list[int]:
        """Mois de la période idéale ; elle peut chevaucher l'année (novembre à mars)."""
        if self.mois_debut is None or self.mois_fin is None:
            return []
        nombre = (self.mois_fin - self.mois_debut) % 12 + 1
        return [(self.mois_debut - 1 + i) % 12 + 1 for i in range(nombre)]

    def periode_ideale(self) -> str:
        mois = self.mois_ideaux()
        if not mois:
            return ""
        if len(mois) == 12:
            return "toute l'année"
        if len(mois) == 1:
            return Mois(mois[0]).label
        debut = Mois(self.mois_debut).label
        de = "d'" if debut[0] in "aeiou" else "de "
        return f"{de}{debut} à {Mois(self.mois_fin).label}"


class Activite(models.Model):
    nom = models.CharField(max_length=150)
    description = models.TextField()
    categorie = models.CharField("catégorie", max_length=20, choices=Categorie.choices)
    duree_minutes = models.PositiveIntegerField(
        "durée (en minutes)", validators=[MinValueValidator(1)]
    )
    prix_par_personne = _champ_prix("prix par personne")
    difficulte = models.CharField("niveau de difficulté", max_length=20, choices=Difficulte.choices)
    age_minimum = models.PositiveSmallIntegerField(
        "âge minimum",
        null=True,
        blank=True,
        validators=[MaxValueValidator(99)],
        help_text="Laisser vide si l'activité convient à tous les âges.",
    )
    # Règle 4 : une activité est proposée dans un seul pays, destination précise optionnelle.
    pays = models.ForeignKey(Pays, on_delete=models.PROTECT, related_name="activites")
    destination = models.ForeignKey(
        Destination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activites",
    )
    actif = models.BooleanField(default=True)

    objects = ActiviteQuerySet.as_manager()

    class Meta:
        verbose_name = "activité"
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom

    def clean(self) -> None:
        super().clean()
        if self.destination_id and self.pays_id and self.destination.pays_id != self.pays_id:
            raise ValidationError(
                {"destination": "La destination doit se trouver dans le pays de l'activité."}
            )

    def duree_affichee(self) -> str:
        heures, minutes = divmod(self.duree_minutes, 60)
        if not heures:
            return f"{minutes} min"
        return f"{heures} h {minutes:02d}" if minutes else f"{heures} h"
