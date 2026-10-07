"""Formulaires de gestion du catalogue (réservés au personnel)."""

from django import forms

from .models import Activite, Destination, Pays


class PaysForm(forms.ModelForm):
    class Meta:
        model = Pays
        fields = (
            "nom",
            "continent",
            "langue_principale",
            "monnaie",
            "description",
            "visa",
            "decalage_ete",
            "decalage_hiver",
            "actif",
        )
        help_texts = {"actif": "Décochez pour masquer ce pays et tout son contenu aux clients."}


class _ContenuDuPaysForm(forms.ModelForm):
    """Le pays est fixé à la création et n'est pas modifiable ensuite."""

    def __init__(self, *args, pays: Pays, **kwargs):
        super().__init__(*args, **kwargs)
        # Le pays doit être connu avant la validation du modèle.
        self.instance.pays = pays


class DestinationForm(_ContenuDuPaysForm):
    class Meta:
        model = Destination
        fields = (
            "nom",
            "description",
            "mois_debut",
            "mois_fin",
            "prix_a_partir_de",
            "photo",
            "actif",
        )
        help_texts = {
            "mois_debut": "Facultatif. La période peut chevaucher l'année (de novembre à mars).",
            "photo": "Facultatif. Adresse complète commençant par https://",
            "actif": "Décochez pour masquer cette destination et ses activités aux clients.",
        }


class ActiviteForm(_ContenuDuPaysForm):
    class Meta:
        model = Activite
        fields = (
            "nom",
            "description",
            "categorie",
            "duree_minutes",
            "prix_par_personne",
            "difficulte",
            "age_minimum",
            "destination",
            "actif",
        )
        help_texts = {
            "duree_minutes": "Par exemple 90 pour 1 h 30.",
            "destination": "Facultatif. Seules les destinations de ce pays sont proposées.",
            "actif": "Décochez pour masquer cette activité aux clients.",
        }

    def __init__(self, *args, pays: Pays, **kwargs):
        super().__init__(*args, pays=pays, **kwargs)
        self.fields["destination"].queryset = pays.destinations.all()
        self.fields["destination"].empty_label = "Aucune destination précise"
