"""Formulaires partagés : champ de date du navigateur et base des filtres des listes du personnel."""

from django import forms

from catalog.models import Country, Destination

PERIOD_ERROR = "La fin de la période doit être après son début."


class DateInput(forms.DateInput):
    """Calendrier du navigateur. La valeur est au format AAAA-MM-JJ, le seul qu'il accepte."""

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs, format="%Y-%m-%d")


def optional_date_field(label: str) -> forms.DateField:
    return forms.DateField(label=label, required=False, widget=DateInput)


class StaffFilterForm(forms.Form):
    """Filtres communs aux listes du personnel (demandes, avis), tous facultatifs.

    Pays et destination, et contrôle des périodes : chaque sous-classe déclare les siennes
    dans `periods`, sous la forme (champ de début, champ de fin).
    """

    periods: tuple[tuple[str, str], ...] = ()

    country = forms.ModelChoiceField(
        label="Pays", required=False, queryset=Country.objects.all(), empty_label="Tous les pays"
    )
    destination = forms.ModelChoiceField(
        label="Destination",
        required=False,
        queryset=Destination.objects.select_related("country").order_by("country__name", "name", "pk"),
        empty_label="Toutes les destinations",
    )

    def clean(self):
        data = super().clean()
        for start, end in self.periods:
            if data.get(start) and data.get(end) and data[end] < data[start]:
                self.add_error(end, PERIOD_ERROR)
        return data
