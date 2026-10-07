"""Recherche dans le catalogue visible : mot-clé et filtres.

Chaque filtre ne concerne que certains types de résultats. Quand un filtre est
utilisé, les types qu'il ne concerne pas sont écartés : par exemple, filtrer par
catégorie ne montre que des activités.
"""

import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q

from .models import Activite, Destination, Pays


def normaliser(texte: str) -> str:
    """Minuscules et sans accents : « Pérou » devient « perou »."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class Criteres:
    mot: str = ""
    continent: str = ""
    categorie: str = ""
    difficulte: str = ""
    budget_max: Decimal | None = None
    mois: int | None = None
    age: int | None = None

    def est_vide(self) -> bool:
        return self == Criteres()


@dataclass
class Resultats:
    pays: list[Pays] = field(default_factory=list)
    destinations: list[Destination] = field(default_factory=list)
    activites: list[Activite] = field(default_factory=list)

    def total(self) -> int:
        return len(self.pays) + len(self.destinations) + len(self.activites)


def _contient_les_mots(objet, mots: list[str]) -> bool:
    texte = normaliser(f"{objet.nom} {objet.description}")
    return all(mot in texte for mot in mots)


def rechercher(criteres: Criteres) -> Resultats:
    filtres_activite = criteres.categorie or criteres.difficulte or criteres.age is not None
    filtre_destination = criteres.mois is not None
    filtre_prix = criteres.budget_max is not None

    resultats = Resultats()
    if not (filtres_activite or filtre_destination or filtre_prix):
        resultats.pays = list(_pays(criteres))
    if not filtres_activite:
        resultats.destinations = list(_destinations(criteres))
    if not filtre_destination:
        resultats.activites = list(_activites(criteres))

    # Recherche par mot en Python : SQLite ne sait pas ignorer les accents.
    mots = normaliser(criteres.mot).split()
    if mots:
        resultats.pays = [p for p in resultats.pays if _contient_les_mots(p, mots)]
        resultats.destinations = [
            d for d in resultats.destinations if _contient_les_mots(d, mots)
        ]
        resultats.activites = [a for a in resultats.activites if _contient_les_mots(a, mots)]
    return resultats


def _pays(criteres: Criteres):
    pays = Pays.objects.visibles()
    if criteres.continent:
        pays = pays.filter(continent=criteres.continent)
    return pays


def _destinations(criteres: Criteres):
    destinations = Destination.objects.visibles().select_related("pays")
    if criteres.continent:
        destinations = destinations.filter(pays__continent=criteres.continent)
    if criteres.budget_max is not None:
        # Une destination sans prix renseigné n'est pas écartée.
        destinations = destinations.filter(
            Q(prix_a_partir_de__isnull=True) | Q(prix_a_partir_de__lte=criteres.budget_max)
        )
    if criteres.mois is not None:
        return [d for d in destinations if criteres.mois in d.mois_ideaux()]
    return destinations


def _activites(criteres: Criteres):
    activites = Activite.objects.visibles().select_related("pays", "destination")
    if criteres.continent:
        activites = activites.filter(pays__continent=criteres.continent)
    if criteres.categorie:
        activites = activites.filter(categorie=criteres.categorie)
    if criteres.difficulte:
        activites = activites.filter(difficulte=criteres.difficulte)
    if criteres.budget_max is not None:
        activites = activites.filter(prix_par_personne__lte=criteres.budget_max)
    if criteres.age is not None:
        activites = activites.filter(
            Q(age_minimum__isnull=True) | Q(age_minimum__lte=criteres.age)
        )
    return activites
