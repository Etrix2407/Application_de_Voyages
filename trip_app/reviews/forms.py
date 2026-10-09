"""Formulaire d'avis du client."""

from django import forms

from catalog.models import Country, Destination

from reviews.services.ratings import BEST_FIRST, NEWEST_FIRST

from reviews.models import (
    MAX_COMMENT_LENGTH,
    MAX_RATING,
    MAX_REFUSAL_DETAILS_LENGTH,
    MAX_RESPONSE_LENGTH,
    MIN_RATING,
    NEGATIVE_RATING,
    RefusalReason,
    Review,
    ReviewStatus,
)

RATING_CHOICES = [
    (rating, f"{rating} étoile{'s' if rating > 1 else ''} sur {MAX_RATING}")
    for rating in range(MAX_RATING, MIN_RATING - 1, -1)
]


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        label="Votre note",
        choices=RATING_CHOICES,
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Choisissez une note."},
    )

    class Meta:
        model = Review
        fields = ("rating", "title", "comment", "anonymous")
        widgets = {"comment": forms.Textarea(attrs={"rows": 6})}
        labels = {"title": "Titre de votre avis", "comment": "Votre commentaire"}
        help_texts = {
            "title": "Une phrase courte, par exemple « Un séjour inoubliable ».",
            "comment": (
                f"Facultatif, sauf pour une note de {NEGATIVE_RATING} étoiles ou moins "
                f"({MAX_COMMENT_LENGTH} caractères au maximum)."
            ),
            "anonymous": (
                "Votre avis sera signé « Voyageur anonyme » au lieu de votre prénom et de l'initiale de votre nom."
            ),
        }


class RefusalForm(forms.Form):
    """Refus ou masquage d'un avis : motif obligatoire, visible par le client."""

    reason = forms.ChoiceField(
        label="Motif",
        choices=[("", "— Choisir un motif —")]
        + [choice for choice in RefusalReason.choices if choice[0] != RefusalReason.TRIP_CANCELLED],
        error_messages={"required": "Le motif est obligatoire."},
    )
    details = forms.CharField(
        label="Précision",
        required=False,
        max_length=MAX_REFUSAL_DETAILS_LENGTH,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Facultative, sauf pour le motif « Autre ». Elle sera visible par le client.",
    )

    def clean(self):
        data = super().clean()
        if data.get("reason") == RefusalReason.OTHER and not data.get("details", "").strip():
            self.add_error("details", "Précisez le motif quand vous choisissez « Autre ».")
        return data


class PublicReviewFilterForm(forms.Form):
    """Tri et filtre des avis d'une destination (fiche publique)."""

    tri = forms.ChoiceField(
        label="Trier",
        required=False,
        choices=[(NEWEST_FIRST, "Les plus récents d'abord"), (BEST_FIRST, "Les meilleures notes d'abord")],
    )
    etoiles = forms.TypedChoiceField(
        label="Nombre d'étoiles",
        required=False,
        coerce=int,
        empty_value=None,
        choices=[("", "Toutes les notes"), *[(rating, label) for rating, label in RATING_CHOICES]],
    )


class ResponseForm(forms.Form):
    text = forms.CharField(
        label="Réponse de l'agence",
        max_length=MAX_RESPONSE_LENGTH,
        widget=forms.Textarea(attrs={"rows": 5}),
        help_text=f"Publique, signée de votre prénom ({MAX_RESPONSE_LENGTH} caractères au maximum).",
        error_messages={"required": "Écrivez la réponse."},
    )


def _date_field(label: str) -> forms.DateField:
    return forms.DateField(label=label, required=False, widget=forms.DateInput(attrs={"type": "date"}))


class StaffReviewFilterForm(forms.Form):
    """Filtres de la liste « Tous les avis » (personnel). Tous facultatifs."""

    status = forms.ChoiceField(label="État", required=False, choices=[("", "Tous les états"), *ReviewStatus.choices])
    country = forms.ModelChoiceField(
        label="Pays", required=False, queryset=Country.objects.all(), empty_label="Tous les pays"
    )
    destination = forms.ModelChoiceField(
        label="Destination",
        required=False,
        queryset=Destination.objects.select_related("country").order_by("country__name", "name", "pk"),
        empty_label="Toutes les destinations",
    )
    rating = forms.TypedChoiceField(
        label="Note", required=False, coerce=int, empty_value=None, choices=[("", "Toutes les notes"), *RATING_CHOICES]
    )
    negative_only = forms.BooleanField(
        label=f"Avis négatifs seulement ({NEGATIVE_RATING} étoiles ou moins)", required=False
    )
    written_from = _date_field("Avis écrit à partir du")
    written_to = _date_field("Avis écrit jusqu'au")
    stay_from = _date_field("Séjour (départ) à partir du")
    stay_to = _date_field("Séjour (départ) jusqu'au")

    def clean(self):
        data = super().clean()
        for start, end in [("written_from", "written_to"), ("stay_from", "stay_to")]:
            if data.get(start) and data.get(end) and data[end] < data[start]:
                self.add_error(end, "La fin de la période doit être après son début.")
        return data
