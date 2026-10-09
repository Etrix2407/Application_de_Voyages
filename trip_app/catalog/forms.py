"""Formulaires du catalogue : gestion (personnel) et recherche."""

from django import forms

from .models import Activity, Category, Continent, Destination, Difficulty, Month, Country
from .services.search import Criteria


class CountryForm(forms.ModelForm):
    class Meta:
        model = Country
        fields = (
            "name",
            "continent",
            "main_language",
            "currency",
            "description",
            "visa",
            "summer_offset",
            "winter_offset",
            "active",
        )
        help_texts = {"active": "Décochez pour masquer ce pays et tout son contenu aux clients."}


class _CountryContentForm(forms.ModelForm):
    """Le pays est fixé à la création et n'est pas modifiable ensuite."""

    def __init__(self, *args, country: Country, **kwargs):
        super().__init__(*args, **kwargs)
        # Le pays doit être connu avant la validation du modèle.
        self.instance.country = country


class DestinationForm(_CountryContentForm):
    class Meta:
        model = Destination
        fields = (
            "name",
            "description",
            "start_month",
            "end_month",
            "price_from",
            "photo",
            "active",
        )
        help_texts = {
            "start_month": "Facultatif. La période peut chevaucher l'année (de novembre à mars).",
            "photo": "Facultatif. Adresse complète commençant par https://",
            "active": "Décochez pour masquer cette destination et ses activités aux clients.",
        }


class ActivityForm(_CountryContentForm):
    class Meta:
        model = Activity
        fields = (
            "name",
            "description",
            "category",
            "duration_minutes",
            "price_per_person",
            "difficulty",
            "minimum_age",
            "destination",
            "active",
        )
        help_texts = {
            "duration_minutes": "Par exemple 90 pour 1 h 30.",
            "destination": "Facultatif. Seules les destinations de ce pays sont proposées.",
            "active": "Décochez pour masquer cette activité aux clients.",
        }

    def __init__(self, *args, country: Country, **kwargs):
        super().__init__(*args, country=country, **kwargs)
        self.fields["destination"].queryset = country.destinations.all()
        self.fields["destination"].empty_label = "Aucune destination précise"


def _with_empty_choice(choices, label: str):
    return [("", label), *choices]


class SearchForm(forms.Form):
    keyword = forms.CharField(
        label="Mot-clé",
        required=False,
        max_length=100,
        help_text="Par exemple : temple, plage, randonnée.",
    )
    continent = forms.ChoiceField(
        required=False, choices=_with_empty_choice(Continent.choices, "Tous les continents")
    )
    category = forms.ChoiceField(
        label="Catégorie d'activité",
        required=False,
        choices=_with_empty_choice(Category.choices, "Toutes les catégories"),
    )
    difficulty = forms.ChoiceField(
        label="Difficulté de l'activité",
        required=False,
        choices=_with_empty_choice(Difficulty.choices, "Toutes les difficultés"),
    )
    max_budget = forms.DecimalField(
        label="Budget maximum (€)",
        required=False,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        help_text="Prix par personne pour une activité, prix « à partir de » pour une destination.",
    )
    month = forms.TypedChoiceField(
        label="Mois de voyage",
        required=False,
        coerce=int,
        empty_value=None,
        choices=_with_empty_choice(Month.choices, "Tous les mois"),
    )
    age = forms.IntegerField(
        label="Âge du voyageur",
        required=False,
        min_value=0,
        max_value=120,
        help_text="Affiche les activités accessibles à cet âge.",
    )

    def criteria(self) -> Criteria:
        """À appeler après is_valid()."""
        return Criteria(**self.cleaned_data)
