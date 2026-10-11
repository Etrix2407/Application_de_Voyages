"""Champ de date du navigateur, commun à tous les formulaires."""

from django import forms


class DateInput(forms.DateInput):
    """Calendrier du navigateur. La valeur est au format AAAA-MM-JJ, le seul qu'il accepte."""

    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs, format="%Y-%m-%d")


def optional_date_field(label: str) -> forms.DateField:
    return forms.DateField(label=label, required=False, widget=DateInput)
