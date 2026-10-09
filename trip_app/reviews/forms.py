"""Formulaire d'avis du client."""

from django import forms

from reviews.models import MAX_COMMENT_LENGTH, MAX_RATING, MIN_RATING, NEGATIVE_RATING, Review

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
