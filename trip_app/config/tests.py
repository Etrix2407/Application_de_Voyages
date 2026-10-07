from django.test import TestCase
from django.urls import reverse


class HomeTests(TestCase):
    def test_home_accessible_without_login(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertTemplateUsed(response, "base.html")

    def test_page_in_french(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<html lang="fr">')


class ErrorPageTests(TestCase):
    def test_readable_not_found_page(self):
        response = self.client.get("/page-qui-n-existe-pas/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "Page introuvable", status_code=404)
