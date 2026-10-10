"""Formulaires du catalogue : gestion (personnel) et recherche."""

from django import forms
from django.utils.html import format_html, format_html_join

from .models import Activity, Category, Continent, Destination, Difficulty, Month, Country
from .services.photos import without_metadata
from .services.time_zones import time_zone_choices, time_zone_from_input, time_zone_label
from .services.search import Criteria
from .validators import PHOTO_FORMATS


class TimeZoneInput(forms.TextInput):
    """Champ texte : en tapant « tok », le navigateur propose « Asie — Tokyo » (balise datalist)."""

    LIST_ID = "time-zone-suggestions"

    def __init__(self):
        super().__init__(attrs={"list": self.LIST_ID, "autocomplete": "off"})

    def render(self, name, value, attrs=None, renderer=None):
        suggestions = format_html_join("", '<option value="{}">', ((label,) for _, label in time_zone_choices()))
        field = super().render(name, value, attrs, renderer)
        return format_html('{}<datalist id="{}">{}</datalist>', field, self.LIST_ID, suggestions)


class CountryForm(forms.ModelForm):
    time_zone = forms.CharField(
        label="Fuseau horaire principal",
        widget=TimeZoneInput(),
        help_text=(
            "Tapez la ville de référence du pays et choisissez-la dans les suggestions, par exemple "
            "« Tokyo » ou « Lima » (pour un pays à plusieurs fuseaux, celle de la destination principale). "
            "Le décalage avec la Belgique est calculé automatiquement, changements d'heure compris."
        ),
        error_messages={"required": "Indiquez le fuseau horaire du pays."},
    )

    class Meta:
        model = Country
        fields = (
            "name",
            "continent",
            "main_language",
            "currency",
            "description",
            "visa",
            "passport_required",
            "time_zone",
            "active",
        )
        help_texts = {
            "passport_required": (
                "Cochez si un passeport valide est obligatoire pour ce pays ; sinon, le rappel envoyé "
                "7 jours avant le départ indique qu'une carte d'identité valide suffit."
            ),
            "active": "Décochez pour masquer ce pays et tout son contenu aux clients.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # En modification, le champ affiche le libellé lisible plutôt que le nom technique.
        if self.instance.time_zone:
            self.initial["time_zone"] = time_zone_label(self.instance.time_zone)

    def clean_time_zone(self) -> str:
        name = time_zone_from_input(self.cleaned_data["time_zone"])
        if name is None:
            raise forms.ValidationError(
                "Fuseau introuvable : tapez le nom d'une ville et choisissez-la dans les suggestions.",
                code="unknown_time_zone",
            )
        return name


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
            "active": "Décochez pour masquer cette destination et ses activités aux clients.",
        }

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        # Pillow lit le vrai format : un GIF renommé en .jpg est refusé.
        image = getattr(photo, "image", None)
        if image is None:
            return photo  # pas de nouvelle photo : celle déjà enregistrée est gardée
        if image.format not in PHOTO_FORMATS:
            raise forms.ValidationError("Formats acceptés : JPEG, PNG ou WebP.", code="invalid_photo_format")
        return without_metadata(photo)


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
