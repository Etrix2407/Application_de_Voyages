from urllib.parse import urlsplit

from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.unsubscribe import unsubscribe_link

from .factories import create_client


class UnsubscribeTests(TestCase):
    def setUp(self):
        self.marie = create_client(accepts_promotional_emails=True)
        self.url = urlsplit(unsubscribe_link(self.marie)).path

    def test_opening_the_link_does_not_unsubscribe(self):
        """Les logiciels qui inspectent les liens ne désinscrivent pas le client à sa place."""
        response = self.client.get(self.url)

        self.assertContains(response, "Me désinscrire")
        self.marie.refresh_from_db()
        self.assertTrue(self.marie.accepts_promotional_emails)

    def test_one_click_unsubscribe_without_login_nor_csrf_token(self):
        """Désinscription directe depuis la messagerie (RFC 8058) : le jeton du lien suffit."""
        response = Client(enforce_csrf_checks=True).post(self.url, {"List-Unsubscribe": "One-Click"})

        self.assertContains(response, "Désinscription confirmée")
        self.marie.refresh_from_db()
        self.assertFalse(self.marie.accepts_promotional_emails)
        self.assertIsNotNone(self.marie.promotional_emails_choice_date)

    def test_invalid_link(self):
        response = self.client.post(reverse("unsubscribe", args=["jeton-invalide"]))

        self.assertContains(response, "Ce lien n'est pas valable")
