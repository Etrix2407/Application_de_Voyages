from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase

from .models import Activite, Categorie, Continent, Destination, Difficulte, Mois, Pays, Visa
from .validators import valider_decalage_horaire


def creer_pays(nom="Japon", **champs):
    donnees = {
        "nom": nom,
        "continent": Continent.ASIE,
        "langue_principale": "japonais",
        "monnaie": "yen",
        "description": "Description du pays.",
        "visa": Visa.NON_REQUIS,
        "decalage_ete": Decimal("7"),
        "decalage_hiver": Decimal("8"),
    }
    donnees.update(champs)
    return Pays.objects.create(**donnees)


def creer_destination(pays, nom="Kyoto", **champs):
    return Destination.objects.create(pays=pays, nom=nom, description="Description.", **champs)


def creer_activite(pays, nom="Cérémonie du thé", **champs):
    donnees = {
        "description": "Description.",
        "categorie": Categorie.CULTURE,
        "duree_minutes": 90,
        "prix_par_personne": Decimal("45.00"),
        "difficulte": Difficulte.FACILE,
    }
    donnees.update(champs)
    return Activite.objects.create(pays=pays, nom=nom, **donnees)


class PaysTests(TestCase):
    def test_nom_unique_sans_tenir_compte_de_la_casse(self):
        creer_pays("Japon")
        doublon = Pays(
            nom="JAPON",
            continent=Continent.ASIE,
            langue_principale="japonais",
            monnaie="yen",
            description="x",
            decalage_ete=0,
            decalage_hiver=0,
        )

        with self.assertRaises(ValidationError) as erreur:
            doublon.full_clean()
        self.assertIn("Un pays avec ce nom existe déjà.", str(erreur.exception))

    def test_pays_vide_supprimable(self):
        pays = creer_pays()

        self.assertTrue(pays.peut_etre_supprime())
        pays.delete()
        self.assertFalse(Pays.objects.exists())

    def test_pays_avec_destination_non_supprimable(self):
        pays = creer_pays()
        creer_destination(pays)

        self.assertFalse(pays.peut_etre_supprime())
        with self.assertRaises(ProtectedError):
            pays.delete()

    def test_pays_avec_activite_non_supprimable(self):
        pays = creer_pays()
        creer_activite(pays)

        self.assertFalse(pays.peut_etre_supprime())
        with self.assertRaises(ProtectedError):
            pays.delete()


class DecalageHoraireTests(SimpleTestCase):
    def test_valeurs_valides(self):
        for valeur in ["-12", "0", "5.5", "5.75", "14"]:
            with self.subTest(valeur=valeur):
                valider_decalage_horaire(Decimal(valeur))

    def test_valeurs_invalides(self):
        for valeur in ["-12.25", "14.5", "5.1", "3.33"]:
            with self.subTest(valeur=valeur), self.assertRaises(ValidationError):
                valider_decalage_horaire(Decimal(valeur))


class PeriodeIdealeTests(SimpleTestCase):
    def periode(self, debut, fin):
        return Destination(mois_debut=debut, mois_fin=fin)

    def test_periode_simple(self):
        destination = self.periode(Mois.AVRIL, Mois.JUIN)

        self.assertEqual(destination.mois_ideaux(), [4, 5, 6])
        self.assertEqual(destination.periode_ideale(), "d'avril à juin")

    def test_periode_qui_chevauche_l_annee(self):
        destination = self.periode(Mois.NOVEMBRE, Mois.MARS)

        self.assertEqual(destination.mois_ideaux(), [11, 12, 1, 2, 3])
        self.assertEqual(destination.periode_ideale(), "de novembre à mars")

    def test_un_seul_mois(self):
        destination = self.periode(Mois.AOUT, Mois.AOUT)

        self.assertEqual(destination.mois_ideaux(), [8])
        self.assertEqual(destination.periode_ideale(), "août")

    def test_toute_l_annee(self):
        self.assertEqual(self.periode(Mois.JANVIER, Mois.DECEMBRE).periode_ideale(), "toute l'année")

    def test_sans_periode(self):
        self.assertEqual(self.periode(None, None).mois_ideaux(), [])
        self.assertEqual(self.periode(None, None).periode_ideale(), "")


class DestinationTests(TestCase):
    def test_champs_facultatifs(self):
        destination = Destination(pays=creer_pays(), nom="Kyoto", description="x")

        destination.full_clean()

    def test_periode_incomplete_refusee(self):
        destination = Destination(
            pays=creer_pays(), nom="Kyoto", description="x", mois_debut=Mois.AVRIL
        )

        with self.assertRaises(ValidationError):
            destination.full_clean()

    def test_suppression_garde_les_activites_dans_le_pays(self):
        pays = creer_pays()
        destination = creer_destination(pays)
        activite = creer_activite(pays, destination=destination)

        destination.delete()

        activite.refresh_from_db()
        self.assertIsNone(activite.destination)
        self.assertEqual(activite.pays, pays)


class ActiviteTests(TestCase):
    def test_destination_d_un_autre_pays_refusee(self):
        japon = creer_pays("Japon")
        perou = creer_pays("Pérou")
        activite = Activite(
            pays=japon,
            destination=creer_destination(perou, "Cusco"),
            nom="Randonnée",
            description="x",
            categorie=Categorie.SPORT,
            duree_minutes=120,
            prix_par_personne=Decimal("30"),
            difficulte=Difficulte.MOYEN,
        )

        with self.assertRaises(ValidationError) as erreur:
            activite.full_clean()
        self.assertIn("destination", erreur.exception.message_dict)

    def test_duree_affichee(self):
        cas = {45: "45 min", 60: "1 h", 90: "1 h 30", 125: "2 h 05"}
        for minutes, attendu in cas.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(Activite(duree_minutes=minutes).duree_affichee(), attendu)


class VisibiliteTests(TestCase):
    def setUp(self):
        self.pays = creer_pays()
        self.destination = creer_destination(self.pays)
        self.activite_sans_destination = creer_activite(self.pays, "Sumo")
        self.activite_avec_destination = creer_activite(
            self.pays, "Temples", destination=self.destination
        )

    def test_tout_visible_si_tout_est_actif(self):
        self.assertEqual(Pays.objects.visibles().count(), 1)
        self.assertEqual(Destination.objects.visibles().count(), 1)
        self.assertEqual(Activite.objects.visibles().count(), 2)

    def test_pays_desactive_masque_tout_son_contenu(self):
        self.pays.actif = False
        self.pays.save()

        self.assertFalse(Pays.objects.visibles().exists())
        self.assertFalse(Destination.objects.visibles().exists())
        self.assertFalse(Activite.objects.visibles().exists())

    def test_destination_desactivee_masque_ses_activites(self):
        self.destination.actif = False
        self.destination.save()

        self.assertFalse(Destination.objects.visibles().exists())
        self.assertEqual(list(Activite.objects.visibles()), [self.activite_sans_destination])

    def test_activite_desactivee_masquee(self):
        self.activite_sans_destination.actif = False
        self.activite_sans_destination.save()

        self.assertEqual(list(Activite.objects.visibles()), [self.activite_avec_destination])
