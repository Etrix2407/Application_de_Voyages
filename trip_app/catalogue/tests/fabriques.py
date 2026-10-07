"""Création de données de test pour le catalogue."""

from decimal import Decimal

from catalogue.models import Activite, Categorie, Continent, Destination, Difficulte, Pays, Visa


def creer_pays(nom="Japon", **champs):
    donnees = {
        "nom": nom,
        "continent": Continent.ASIE,
        "langue_principale": "japonais",
        "monnaie": "yen",
        "description": "Description du pays.",
        "visa": Visa.NON_REQUIS,
        "decalage_ete": Decimal("7"),
        "decalage_hiver": Decimal("8"),
    }
    donnees.update(champs)
    return Pays.objects.create(**donnees)


def creer_destination(pays, nom="Kyoto", **champs):
    return Destination.objects.create(pays=pays, nom=nom, description="Description.", **champs)


def creer_activite(pays, nom="Cérémonie du thé", **champs):
    donnees = {
        "description": "Description.",
        "categorie": Categorie.CULTURE,
        "duree_minutes": 90,
        "prix_par_personne": Decimal("45.00"),
        "difficulte": Difficulte.FACILE,
    }
    donnees.update(champs)
    return Activite.objects.create(pays=pays, nom=nom, **donnees)
