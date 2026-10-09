from django.test import TestCase
from django.urls import reverse


class HomeTests(TestCase):
    def test_page_in_french(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<html lang="fr">')

    def test_browser_spellcheck_disabled(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<body spellcheck="false">')

    def test_site_name_in_title_header_and_footer(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "<title>Accueil — Horizons Lointains</title>", html=False)
        self.assertContains(response, "Horizons Lointains", count=3)


class ErrorPageTests(TestCase):
    def test_readable_not_found_page(self):
        response = self.client.get("/page-qui-n-existe-pas/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page introuvable", status_code=404)
