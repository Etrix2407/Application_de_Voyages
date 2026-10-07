from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from catalogue.models import Categorie, Continent, Difficulte, Mois
from catalogue.recherche import Criteres, normaliser, rechercher

from .fabriques import creer_activite, creer_destination, creer_pays

Utilisateur = get_user_model()


def noms(objets):
    return sorted(objet.nom for objet in objets)


class NormaliserTests(SimpleTestCase):
    def test_ignore_accents_et_majuscules(self):
        self.assertEqual(normaliser("PÉROU Île Çà"), "perou ile ca")


class RechercheTests(TestCase):
    def setUp(self):
        self.japon = creer_pays("Japon", continent=Continent.ASIE, description="Temples et sushis.")
        self.perou = creer_pays("Pérou", continent=Continent.AMERIQUE, description="Andes.")
        self.kyoto = creer_destination(
            self.japon,
            "Kyoto",
            description="Ancienne capitale, temples.",
            mois_debut=Mois.NOVEMBRE,
            mois_fin=Mois.MARS,
            prix_a_partir_de=Decimal("1500"),
        )
        self.cusco = creer_destination(
            self.perou, "Cusco", description="Porte du Machu Picchu.", mois_debut=Mois.MAI, mois_fin=Mois.SEPTEMBRE
        )
        self.the = creer_activite(
            self.japon,
            "Cérémonie du thé",
            description="Tradition japonaise.",
            categorie=Categorie.CULTURE,
            prix_par_personne=Decimal("45"),
            difficulte=Difficulte.FACILE,
            destination=self.kyoto,
        )
        self.trek = creer_activite(
            self.perou,
            "Trek de l'Inca",
            description="Randonnée vers le Machu Picchu.",
            categorie=Categorie.AVENTURE,
            prix_par_personne=Decimal("600"),
            difficulte=Difficulte.DIFFICILE,
            age_minimum=16,
        )

    def test_mot_sans_accent_ni_majuscule(self):
        resultats = rechercher(Criteres(mot="perou"))

        self.assertEqual(noms(resultats.pays), ["Pérou"])

    def test_mot_dans_le_nom_ou_la_description(self):
        resultats = rechercher(Criteres(mot="temples"))

        self.assertEqual(noms(resultats.pays), ["Japon"])
        self.assertEqual(noms(resultats.destinations), ["Kyoto"])
        self.assertEqual(resultats.activites, [])

    def test_plusieurs_mots_tous_requis(self):
        resultats = rechercher(Criteres(mot="machu randonnee"))

        self.assertEqual(noms(resultats.activites), ["Trek de l'Inca"])
        self.assertEqual(resultats.destinations, [])

    def test_continent(self):
        resultats = rechercher(Criteres(continent=Continent.AMERIQUE))

        self.assertEqual(noms(resultats.pays), ["Pérou"])
        self.assertEqual(noms(resultats.destinations), ["Cusco"])
        self.assertEqual(noms(resultats.activites), ["Trek de l'Inca"])

    def test_categorie_ne_montre_que_des_activites(self):
        resultats = rechercher(Criteres(categorie=Categorie.CULTURE))

        self.assertEqual(noms(resultats.activites), ["Cérémonie du thé"])
        self.assertEqual(resultats.pays, [])
        self.assertEqual(resultats.destinations, [])

    def test_difficulte(self):
        resultats = rechercher(Criteres(difficulte=Difficulte.DIFFICILE))

        self.assertEqual(noms(resultats.activites), ["Trek de l'Inca"])

    def test_budget_sur_activites_et_destinations(self):
        resultats = rechercher(Criteres(budget_max=Decimal("100")))

        self.assertEqual(noms(resultats.activites), ["Cérémonie du thé"])
        # Kyoto (1500 €) est écartée ; Cusco (sans prix) est gardée.
        self.assertEqual(noms(resultats.destinations), ["Cusco"])
        self.assertEqual(resultats.pays, [])

    def test_budget_inclut_le_prix_exact(self):
        resultats = rechercher(Criteres(budget_max=Decimal("1500")))

        self.assertIn("Kyoto", noms(resultats.destinations))

    def test_mois_ne_montre_que_des_destinations(self):
        resultats = rechercher(Criteres(mois=Mois.JANVIER))

        self.assertEqual(noms(resultats.destinations), ["Kyoto"])
        self.assertEqual(resultats.activites, [])

    def test_mois_exclut_les_destinations_sans_periode(self):
        creer_destination(self.japon, "Osaka")

        resultats = rechercher(Criteres(mois=Mois.JANVIER))

        self.assertNotIn("Osaka", noms(resultats.destinations))

    def test_age_du_voyageur(self):
        self.assertEqual(noms(rechercher(Criteres(age=10)).activites), ["Cérémonie du thé"])
        self.assertEqual(
            noms(rechercher(Criteres(age=16)).activites), ["Cérémonie du thé", "Trek de l'Inca"]
        )

    def test_filtres_combines(self):
        resultats = rechercher(
            Criteres(mot="the", continent=Continent.ASIE, budget_max=Decimal("50"))
        )

        self.assertEqual(noms(resultats.activites), ["Cérémonie du thé"])

    def test_elements_desactives_exclus(self):
        self.perou.actif = False
        self.perou.save()

        resultats = rechercher(Criteres(mot="machu"))

        self.assertEqual(resultats.total(), 0)


class PageRechercheTests(TestCase):
    url = reverse("recherche")

    def setUp(self):
        self.client.force_login(
            Utilisateur.objects.create_user(
                "c@example.com", "voyage2026ok", nom="D", prenom="M", date_naissance=date(1950, 1, 1)
            )
        )
        creer_activite(creer_pays("Japon"), "Cérémonie du thé", categorie=Categorie.CULTURE)

    def test_connexion_requise(self):
        self.client.logout()

        self.assertRedirects(self.client.get(self.url), f"{reverse('connexion')}?next={self.url}")

    def test_formulaire_vide_sans_resultats(self):
        reponse = self.client.get(self.url)

        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.context["resultats"])

    def test_resultats_affiches(self):
        reponse = self.client.get(self.url, {"mot": "CEREMONIE"})

        self.assertContains(reponse, "1 résultat")
        self.assertContains(reponse, "Cérémonie du thé")

    def test_aucun_resultat(self):
        reponse = self.client.get(self.url, {"mot": "volcan"})

        self.assertContains(reponse, "Aucun résultat")

    def test_valeurs_invalides(self):
        reponse = self.client.get(self.url, {"budget_max": "-5", "age": "abc"})

        self.assertIsNone(reponse.context["resultats"])
        self.assertTrue(reponse.context["form"].errors)
