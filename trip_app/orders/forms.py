"""Formulaire de demande de voyage (client)."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from catalog.models import Activity, Country, Destination
from orders.models import MIN_DAYS_BEFORE_DEPARTURE, Order, Status
from orders.services.filtering import NEWEST_FIRST, OLDEST_FIRST


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


class ClientCancelForm(forms.Form):
    reason = forms.CharField(
        label="Motif (facultatif)",
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Nous aide à mieux vous servir, mais vous pouvez le laisser vide.",
    )


class StaffOrderFilterForm(forms.Form):
    """Filtres de la liste des demandes (personnel). Tous facultatifs."""

    status = forms.ChoiceField(label="État", required=False, choices=[("", "Tous les états"), *Status.choices])
    country = forms.ModelChoiceField(
        label="Pays", required=False, queryset=Country.objects.all(), empty_label="Tous les pays"
    )
    destination = forms.ModelChoiceField(
        label="Destination",
        required=False,
        queryset=Destination.objects.select_related("country").order_by("country__name", "name", "pk"),
        empty_label="Toutes les destinations",
    )
    client = forms.CharField(
        label="Client", required=False, max_length=100, help_text="Nom, prénom ou e-mail."
    )
    departure_from = forms.DateField(
        label="Départ à partir du", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    departure_to = forms.DateField(
        label="Départ jusqu'au", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    sort = forms.ChoiceField(
        label="Tri",
        required=False,
        choices=[(NEWEST_FIRST, "Demandes les plus récentes d'abord"), (OLDEST_FIRST, "Demandes les plus anciennes d'abord")],
    )

    def clean(self):
        data = super().clean()
        start, end = data.get("departure_from"), data.get("departure_to")
        if start and end and end < start:
            raise forms.ValidationError("La fin de la période doit être après son début.")
        return data


class StaffCancelForm(forms.Form):
    reason = forms.CharField(
        label="Motif de l'annulation",
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Obligatoire. Il apparaîtra dans l'historique de la demande, visible par le client.",
        error_messages={"required": "Le motif est obligatoire."},
    )
