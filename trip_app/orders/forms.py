"""Formulaire de demande de voyage (client)."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from catalog.models import Activity, Destination
from orders.models import MIN_DAYS_BEFORE_DEPARTURE, Order


class ActivityChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, activity: Activity) -> str:
        # L'âge minimum est affiché pour information, il n'est pas vérifié.
        age = f", à partir de {activity.minimum_age} ans" if activity.minimum_age else ""
        return f"{activity.name} — {activity.price_per_person} € par personne ({activity.duration_display()}{age})"


class OrderForm(forms.ModelForm):
    activities = ActivityChoiceField(
        label="Activités souhaitées",
        queryset=Activity.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Facultatif. Le prix des enfants est compté à 50 %, activités comprises.",
    )

    class Meta:
        model = Order
        fields = ("departure_date", "return_date", "adults", "children", "remarks")
        widgets = {
            "departure_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "return_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "adults": forms.NumberInput(attrs={"min": 1, "max": 10}),
            "children": forms.NumberInput(attrs={"min": 0, "max": 9}),
            "remarks": forms.Textarea(attrs={"rows": 4}),
        }
        help_texts = {
            "departure_date": f"Au moins {MIN_DAYS_BEFORE_DEPARTURE} jours après aujourd'hui.",
            "children": "Au total, 10 voyageurs maximum.",
            "remarks": "Facultatif : vos souhaits, questions, contraintes…",
        }

    def __init__(self, *args, client, destination: Destination, **kwargs):
        super().__init__(*args, **kwargs)
        # Connus avant la validation du modèle (destination proposée, règles de dates).
        self.instance.client = client
        self.instance.destination = destination
        self.fields["activities"].queryset = Activity.objects.visible().filter(country=destination.country)
        earliest = timezone.localdate() + timedelta(days=MIN_DAYS_BEFORE_DEPARTURE)
        self.fields["departure_date"].widget.attrs["min"] = earliest.isoformat()
        self.fields["return_date"].widget.attrs["min"] = (earliest + timedelta(days=1)).isoformat()
