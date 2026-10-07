from django.test import TestCase
from django.urls import reverse

from catalogue.models import FavoriActivite, FavoriDestination
from comptes.tests.fabriques import MOT_DE_PASSE, creer_agent, creer_client

from .fabriques import creer_activite, creer_destination, creer_pays


class FavorisTests(TestCase):
    def setUp(self):
        self.client_marie = creer_client()
        self.client.force_login(self.client_marie)
        self.pays = creer_pays()
        self.destination = creer_destination(self.pays, "Kyoto")
        self.activite = creer_activite(self.pays, "Sumo")

    def ajouter(self, type_element, pk, **donnees):
        return self.client.post(reverse("ajouter_favori", args=[type_element, pk]), donnees)

    def retirer(self, type_element, pk, **donnees):
        return self.client.post(reverse("retirer_favori", args=[type_element, pk]), donnees)

    def test_ajouter_une_destination_revient_a_sa_page(self):
        reponse = self.ajouter("destination", self.destination.pk)

        self.assertRedirects(reponse, reverse("detail_destination", args=[self.destination.pk]))
        self.assertTrue(
            FavoriDestination.objects.filter(client=self.client_marie, destination=self.destination).exists()
        )

    def test_ajouter_deux_fois_ne_cree_pas_de_doublon(self):
        self.ajouter("activite", self.activite.pk)
        self.ajouter("activite", self.activite.pk)

        self.assertEqual(FavoriActivite.objects.count(), 1)

    def test_element_masque_non_ajoutable(self):
        self.destination.actif = False
        self.destination.save()

        self.assertEqual(self.ajouter("destination", self.destination.pk).status_code, 404)

    def test_type_inconnu(self):
        self.assertEqual(self.ajouter("pays", self.pays.pk).status_code, 404)

    def test_get_refuse(self):
        url = reverse("ajouter_favori", args=["activite", self.activite.pk])

        self.assertEqual(self.client.get(url).status_code, 405)

    def test_retirer(self):
        self.ajouter("activite", self.activite.pk)

        reponse = self.retirer("activite", self.activite.pk)

        self.assertRedirects(reponse, reverse("mes_favoris"))
        self.assertFalse(FavoriActivite.objects.exists())

    def test_redirection_externe_ou_invalide_ignoree(self):
        detail = reverse("detail_activite", args=[self.activite.pk])
        for suivant in [
            "https://pirate.example.com/",
            "//pirate.example.com/",
            "admin'--",
            "' OR '1'='1",
            "mes_favoris",
        ]:
            with self.subTest(suivant=suivant):
                reponse = self.ajouter("activite", self.activite.pk, suivant=suivant)

                self.assertRedirects(reponse, detail)

    def test_retour_a_la_page_d_origine(self):
        reponse = self.retirer("activite", self.activite.pk, suivant="/catalogue/favoris/")

        self.assertRedirects(reponse, reverse("mes_favoris"))

    def test_bouton_sur_les_pages_de_detail(self):
        url = reverse("detail_activite", args=[self.activite.pk])

        self.assertContains(self.client.get(url), "Ajouter à mes favoris")
        self.ajouter("activite", self.activite.pk)
        self.assertContains(self.client.get(url), "Retirer de mes favoris")

    def test_mes_favoris(self):
        self.ajouter("destination", self.destination.pk)
        self.ajouter("activite", self.activite.pk)

        reponse = self.client.get(reverse("mes_favoris"))

        self.assertContains(reponse, reverse("detail_destination", args=[self.destination.pk]))
        self.assertContains(reponse, reverse("detail_activite", args=[self.activite.pk]))

    def test_favori_desactive_affiche_indisponible(self):
        self.ajouter("activite", self.activite.pk)
        self.pays.actif = False
        self.pays.save()

        reponse = self.client.get(reverse("mes_favoris"))

        self.assertContains(reponse, "Sumo")
        self.assertContains(reponse, "plus disponible")
        self.assertNotContains(reponse, reverse("detail_activite", args=[self.activite.pk]))
        self.assertContains(reponse, "Retirer de mes favoris")

    def test_chaque_client_ne_voit_que_ses_favoris(self):
        autre = creer_client("autre@example.com")
        FavoriActivite.objects.create(client=autre, activite=self.activite)

        reponse = self.client.get(reverse("mes_favoris"))

        self.assertNotContains(reponse, "Sumo")

    def test_retirer_le_favori_d_un_autre_client_sans_effet(self):
        autre = creer_client("autre@example.com")
        FavoriActivite.objects.create(client=autre, activite=self.activite)

        self.retirer("activite", self.activite.pk)

        self.assertTrue(FavoriActivite.objects.filter(client=autre).exists())

    def test_favoris_supprimes_avec_le_compte(self):
        self.ajouter("activite", self.activite.pk)

        self.client.post(reverse("supprimer_compte"), {"mot_de_passe": MOT_DE_PASSE})

        self.assertFalse(FavoriActivite.objects.exists())


class AccesFavorisTests(TestCase):
    def test_reserve_aux_clients(self):
        activite = creer_activite(creer_pays())
        self.client.force_login(creer_agent())

        self.assertEqual(self.client.get(reverse("mes_favoris")).status_code, 403)
        url = reverse("ajouter_favori", args=["activite", activite.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertNotContains(
            self.client.get(reverse("detail_activite", args=[activite.pk])), "mes favoris"
        )

    def test_visiteur_redirige(self):
        url = reverse("mes_favoris")

        self.assertRedirects(self.client.get(url), f"{reverse('connexion')}?next={url}")
