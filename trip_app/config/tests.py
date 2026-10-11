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


class SecurityHeaderTests(TestCase):
    def test_content_security_policy_forbids_inline_scripts_and_framing(self):
        response = self.client.get(reverse("home"))

        policy = response.headers["Content-Security-Policy"]
        self.assertIn("script-src 'self'", policy)
        self.assertIn("frame-ancestors 'none'", policy)


class ErrorPageTests(TestCase):
    def test_readable_not_found_page(self):
        response = self.client.get("/page-qui-n-existe-pas/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page introuvable", status_code=404)
