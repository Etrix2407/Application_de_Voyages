from django import forms
from django.utils import timezone

from catalog.models import Country, Destination
from promotions.models import Promotion, Scope, targets_problem

_DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class DestinationChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, destination) -> str:
        return f"{destination.name} ({destination.country.name})"


class PromotionForm(forms.ModelForm):
    countries = forms.ModelMultipleChoiceField(
        label="Pays visés",
        queryset=Country.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Seulement pour la portée « Un ou plusieurs pays ».",
    )
    destinations = DestinationChoiceField(
        label="Destinations visées",
        queryset=Destination.objects.select_related("country").order_by("country__name", "name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Seulement pour la portée « Une ou plusieurs destinations ».",
    )

    class Meta:
        model = Promotion
        fields = [
            "name", "description", "kind", "value", "scope", "countries", "destinations", "base",
            "starts_on", "ends_on", "departure_from", "departure_until", "code", "max_uses", "max_uses_per_client",
        ]
        widgets = {
            "starts_on": _DATE,
            "ends_on": _DATE,
            "departure_from": _DATE,
            "departure_until": _DATE,
            "description": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "starts_on": "La promotion vaut pour les demandes faites à partir de ce jour.",
            "ends_on": "Dernier jour inclus, jusqu'à minuit.",
            "departure_from": "Facultatif : départs autorisés. Vide = tous les départs.",
            "code": "Vide = promotion automatique. Sinon 4 à 20 lettres sans accents ou chiffres (ex. BIENVENUE15).",
            "max_uses": "Vide = illimité. Les demandes annulées ne comptent pas.",
            "max_uses_per_client": "Vide = illimité.",
        }

    # Une promotion déjà utilisée ne change plus que ces champs : sa valeur, sa portée, etc.
    # restent celles appliquées aux demandes. Pour les changer, on crée une nouvelle promotion.
    EDITABLE_ONCE_USED = ("name", "description", "ends_on")

    def __init__(self, *args, used: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if used:
            for name, field in self.fields.items():
                field.disabled = name not in self.EDITABLE_ONCE_USED

    def clean_ends_on(self):
        ends_on = self.cleaned_data["ends_on"]
        # Avancer la fin est permis, pas la placer dans le passé : pour arrêter, on désactive.
        if "ends_on" in self.changed_data and ends_on and ends_on < timezone.localdate():
            raise forms.ValidationError(
                "La date de fin ne peut pas être dans le passé. Pour arrêter la promotion, désactivez-la."
            )
        return ends_on

    def clean(self):
        data = super().clean()
        scope = data.get("scope")
        for field, message in targets_problem(scope, data.get("countries"), data.get("destinations")).items():
            self.add_error(field, message)
        # Seule la liste qui correspond à la portée est gardée.
        if scope != Scope.COUNTRIES:
            data["countries"] = []
        if scope != Scope.DESTINATIONS:
            data["destinations"] = []
        return data
