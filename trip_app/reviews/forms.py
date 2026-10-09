"""Formulaire d'avis du client."""

from django import forms

from reviews.services.ratings import BEST_FIRST, NEWEST_FIRST

from reviews.models import (
    MAX_COMMENT_LENGTH,
    MAX_RATING,
    MAX_REFUSAL_DETAILS_LENGTH,
    MIN_RATING,
    NEGATIVE_RATING,
    RefusalReason,
    Review,
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
