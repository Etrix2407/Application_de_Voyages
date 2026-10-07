"""Formulaires du catalogue : gestion (personnel) et recherche."""

from django import forms

from .models import Activite, Categorie, Continent, Destination, Difficulte, Mois, Pays
from .recherche import Criteres


class PaysForm(forms.ModelForm):
    class Meta:
        model = Pays
        fields = (
            "nom",
            "continent",
            "langue_principale",
            "monnaie",
            "description",
            "visa",
            "decalage_ete",
            "decalage_hiver",
            "actif",
        )
        help_texts = {"actif": "Décochez pour masquer ce pays et tout son contenu aux clients."}


class _ContenuDuPaysForm(forms.ModelForm):
    """Le pays est fixé à la création et n'est pas modifiable ensuite."""

    def __init__(self, *args, pays: Pays, **kwargs):
        super().__init__(*args, **kwargs)
        # Le pays doit être connu avant la validation du modèle.
        self.instance.pays = pays


class DestinationForm(_ContenuDuPaysForm):
    class Meta:
        model = Destination
        fields = (
            "nom",
            "description",
            "mois_debut",
            "mois_fin",
            "prix_a_partir_de",
            "photo",
            "actif",
        )
        help_texts = {
            "mois_debut": "Facultatif. La période peut chevaucher l'année (de novembre à mars).",
            "photo": "Facultatif. Adresse complète commençant par https://",
            "actif": "Décochez pour masquer cette destination et ses activités aux clients.",
        }


class ActiviteForm(_ContenuDuPaysForm):
    class Meta:
        model = Activite
        fields = (
            "nom",
            "description",
            "categorie",
            "duree_minutes",
            "prix_par_personne",
            "difficulte",
            "age_minimum",
            "destination",
            "actif",
        )
        help_texts = {
            "duree_minutes": "Par exemple 90 pour 1 h 30.",
            "destination": "Facultatif. Seules les destinations de ce pays sont proposées.",
            "actif": "Décochez pour masquer cette activité aux clients.",
        }

    def __init__(self, *args, pays: Pays, **kwargs):
        super().__init__(*args, pays=pays, **kwargs)
        self.fields["destination"].queryset = pays.destinations.all()
        self.fields["destination"].empty_label = "Aucune destination précise"


def _avec_choix_vide(choix, libelle: str):
    return [("", libelle), *choix]


class RechercheForm(forms.Form):
    mot = forms.CharField(
        label="Mot-clé",
        required=False,
        max_length=100,
        help_text="Par exemple : temple, plage, randonnée.",
    )
    continent = forms.ChoiceField(
        required=False, choices=_avec_choix_vide(Continent.choices, "Tous les continents")
    )
    categorie = forms.ChoiceField(
        label="Catégorie d'activité",
        required=False,
        choices=_avec_choix_vide(Categorie.choices, "Toutes les catégories"),
    )
    difficulte = forms.ChoiceField(
        label="Difficulté de l'activité",
        required=False,
        choices=_avec_choix_vide(Difficulte.choices, "Toutes les difficultés"),
    )
    budget_max = forms.DecimalField(
        label="Budget maximum (€)",
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        help_text="Prix par personne pour une activité, prix « à partir de » pour une destination.",
    )
    mois = forms.TypedChoiceField(
        label="Mois de voyage",
        required=False,
        coerce=int,
        empty_value=None,
        choices=_avec_choix_vide(Mois.choices, "Tous les mois"),
    )
    age = forms.IntegerField(
        label="Âge du voyageur",
        required=False,
        min_value=0,
        max_value=120,
        help_text="Affiche les activités accessibles à cet âge.",
    )

    def criteres(self) -> Criteres:
        """À appeler après is_valid()."""
        return Criteres(**self.cleaned_data)
