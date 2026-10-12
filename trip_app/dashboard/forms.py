"""Formulaire de période du tableau de pilotage (GET)."""

from django import forms

from catalog.forms import PERIOD_ERROR
from common.forms import DateInput
from dashboard.services.periods import (
    MAX_CUSTOM_DAYS,
    DateBasis,
    Period,
    Shortcut,
    custom_period,
    default_period,
    shortcut_period,
)

CUSTOM_DATE_HELP = "Seulement pour une période personnalisée."


class PeriodForm(forms.Form):
    shortcut = forms.ChoiceField(label="Période", choices=Shortcut.choices, initial=Shortcut.THIS_MONTH)
    basis = forms.ChoiceField(label="Compter les commandes selon", choices=DateBasis.choices, initial=DateBasis.ORDERED)
    start = forms.DateField(label="Du", required=False, widget=DateInput, help_text=CUSTOM_DATE_HELP)
    end = forms.DateField(label="Au", required=False, widget=DateInput, help_text=CUSTOM_DATE_HELP)

    def clean(self):
        data = super().clean()
        if data.get("shortcut") != Shortcut.CUSTOM:
            return data
        start, end = data.get("start"), data.get("end")
        for name, value in (("start", start), ("end", end)):
            if not value and name not in self.errors:
                self.add_error(name, "Obligatoire pour une période personnalisée.")
        if start and end:
            if end < start:
                self.add_error("end", PERIOD_ERROR)
            elif (end - start).days + 1 > MAX_CUSTOM_DAYS:
                self.add_error("end", "La période ne peut pas dépasser 5 ans.")
        return data

    def period(self) -> Period:
        """Période demandée ; ce mois-ci par date de commande si rien n'est demandé ou si c'est invalide."""
        if not self.is_bound or not self.is_valid():
            return default_period()
        data = self.cleaned_data
        if data["shortcut"] == Shortcut.CUSTOM:
            return custom_period(data["start"], data["end"], data["basis"])
        return shortcut_period(data["shortcut"], data["basis"])
