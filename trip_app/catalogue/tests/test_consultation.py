from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from catalogue.models import Continent, afficher_decalage

from .fabriques import creer_activite, creer_destination, creer_pays

Utilisateur = get_user_model()


def creer_client():
    return Utilisateur.objects.create_user(
        "client@example.com",
        "voyage2026ok",
        nom="Dupont",
        prenom="Marie",
        date_naissance=date(1955, 4, 12),
    )


class AfficherDecalageTests(SimpleTestCase):
    def test_formats(self):
        cas = {
            "0": "même heure qu'en Belgique",
            "7": "+7 h",
            "-6": "-6 h",
            "3.5": "+3 h 30",
            "5.75": "+5 h 45",
            "-2.5": "-2 h 30",
        }
        for valeur, attendu in cas.items():
            with self.subTest(valeur=valeur):
                self.assertEqual(afficher_decalage(Decimal(valeur)), attendu)


class ListePaysTests(TestCase):
    url = reverse("catalogue_pays")

    def test_visible_sans_connexion_et_groupee_par_continent(self):
        creer_pays("Japon", continent=Continent.ASIE, description="Pays du soleil levant.")
        creer_pays("Pérou", continent=Continent.AMERIQUE)

        reponse = self.client.get(self.url)

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            [(continent, [p.nom for p in pays]) for continent, pays in reponse.context["continents"]],
            [("Amérique", ["Pérou"]), ("Asie", ["Japon"])],
        )
        self.assertContains(reponse, "Pays du soleil levant.")
        self.assertContains(reponse, "Connectez-vous")

    def test_pays_desactive_masque(self):
        creer_pays("Cuba", actif=False)

        self.assertNotContains(self.client.get(self.url), "Cuba")

    def test_description_tronquee(self):
        creer_pays(description=" ".join(["mot"] * 40))

        reponse = self.client.get(self.url)

        self.assertContains(reponse, "mot …")


class AccesDetailTests(TestCase):
    def setUp(self):
        self.pays = creer_pays()
        self.destination = creer_destination(self.pays)
        self.activite = creer_activite(self.pays)

    def test_details_reserves_aux_utilisateurs_connectes(self):
        urls = [
            reverse("detail_pays", args=[self.pays.pk]),
            reverse("detail_destination", args=[self.destination.pk]),
            reverse("detail_activite", args=[self.activite.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('connexion')}?next={url}")

                self.client.force_login(creer_client())
                self.assertEqual(self.client.get(url).status_code, 200)
                self.client.logout()
                Utilisateur.objects.all().delete()


class DetailPaysTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_client())
        self.pays = creer_pays("Japon", decalage_ete=Decimal("7"), decalage_hiver=Decimal("8"))

    def test_affiche_les_informations_et_le_contenu_visible(self):
        creer_destination(self.pays, "Kyoto", photo="https://example.com/kyoto.jpg")
        creer_destination(self.pays, "Osaka", actif=False)
        creer_activite(self.pays, "Sumo")
        creer_activite(self.pays, "Karaoké", actif=False)

        reponse = self.client.get(reverse("detail_pays", args=[self.pays.pk]))

        self.assertContains(reponse, "+7 h en été, +8 h en hiver")
        self.assertContains(reponse, "Kyoto")
        self.assertContains(reponse, 'alt="Photo : Kyoto"')
        self.assertContains(reponse, "Sumo")
        self.assertNotContains(reponse, "Osaka")
        self.assertNotContains(reponse, "Karaoké")

    def test_pays_desactive_introuvable(self):
        self.pays.actif = False
        self.pays.save()

        self.assertEqual(self.client.get(reverse("detail_pays", args=[self.pays.pk])).status_code, 404)


class DetailDestinationTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_client())
        self.pays = creer_pays()
        self.destination = creer_destination(self.pays, "Kyoto")

    def test_affiche_ses_activites_seulement(self):
        creer_activite(self.pays, "Temples", destination=self.destination)
        creer_activite(self.pays, "Sumo")

        reponse = self.client.get(reverse("detail_destination", args=[self.destination.pk]))

        self.assertContains(reponse, "Temples")
        self.assertNotContains(reponse, "Sumo")

    def test_destination_masquee_si_elle_ou_son_pays_est_desactive(self):
        url = reverse("detail_destination", args=[self.destination.pk])

        self.pays.actif = False
        self.pays.save()
        self.assertEqual(self.client.get(url).status_code, 404)

        self.pays.actif = True
        self.pays.save()
        self.destination.actif = False
        self.destination.save()
        self.assertEqual(self.client.get(url).status_code, 404)


class DetailActiviteTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_client())
        self.pays = creer_pays("Japon")

    def test_affiche_le_detail(self):
        destination = creer_destination(self.pays, "Kyoto")
        activite = creer_activite(
            self.pays, "Temples", destination=destination, duree_minutes=90, age_minimum=12
        )

        reponse = self.client.get(reverse("detail_activite", args=[activite.pk]))

        self.assertContains(reponse, "1 h 30")
        self.assertContains(reponse, "12 ans")
        self.assertContains(reponse, "Facile")
        self.assertContains(reponse, reverse("detail_destination", args=[destination.pk]))

    def test_tous_ages_si_pas_d_age_minimum(self):
        activite = creer_activite(self.pays)

        reponse = self.client.get(reverse("detail_activite", args=[activite.pk]))

        self.assertContains(reponse, "Tous âges")

    def test_activite_d_une_destination_desactivee_masquee(self):
        destination = creer_destination(self.pays, actif=False)
        activite = creer_activite(self.pays, destination=destination)

        reponse = self.client.get(reverse("detail_activite", args=[activite.pk]))

        self.assertEqual(reponse.status_code, 404)
