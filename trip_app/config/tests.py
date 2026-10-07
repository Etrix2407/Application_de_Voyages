from django.test import TestCase
from django.urls import reverse


class AccueilTests(TestCase):
    def test_accueil_accessible_sans_connexion(self):
        reponse = self.client.get(reverse("accueil"))

        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, "accueil.html")
        self.assertTemplateUsed(reponse, "base.html")

    def test_page_en_francais(self):
        reponse = self.client.get(reverse("accueil"))

        self.assertContains(reponse, '<html lang="fr">')
