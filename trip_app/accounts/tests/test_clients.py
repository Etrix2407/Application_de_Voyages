import re
from unittest import mock
from datetime import date

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role
from accounts.views.clients import CLIENTS_PER_PAGE

from .email_delivery import SendEmailsImmediately
from .factories import PASSWORD, create_agent, create_client


class ClientAccessTests(TestCase):
    def test_staff_accounts_inaccessible(self):
        agent = create_agent()
        self.client.force_login(agent)

        self.assertEqual(
            self.client.get(reverse("edit_client", args=[agent.pk])).status_code, 404
        )


class ClientListTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())

    def test_lists_clients_without_staff(self):
        create_client()

        response = self.client.get(reverse("client_list"))

        self.assertContains(response, "client@example.com")
        self.assertNotContains(response, "agent@example.com</td>")

    def test_search_without_accents(self):
        create_client("helene@example.com", last_name="Lefèvre", first_name="Hélène")
        create_client("paul@example.com", last_name="Durand", first_name="Paul")

        response = self.client.get(reverse("client_list"), {"q": "helene LEFEVRE"})

        self.assertContains(response, "helene@example.com")
        self.assertNotContains(response, "paul@example.com")

    def test_pagination(self):
        for i in range(CLIENTS_PER_PAGE + 1):
            create_client(f"client{i:02d}@example.com", last_name=f"Nom{i:02d}")

        page_1 = self.client.get(reverse("client_list"))
        page_2 = self.client.get(reverse("client_list"), {"page": 2})

        self.assertEqual(len(page_1.context["page"].object_list), CLIENTS_PER_PAGE)
        self.assertContains(page_1, "Page suivante")
        self.assertEqual(len(page_2.context["page"].object_list), 1)
        self.assertContains(page_2, "Page précédente")

    def test_invalid_page_shows_last(self):
        create_client()

        response = self.client.get(reverse("client_list"), {"page": "999"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "client@example.com")


class ClientCorrectionTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.marie = create_client()
        self.url = reverse("edit_client", args=[self.marie.pk])

    def test_correct_information(self):
        response = self.client.post(
            self.url,
            {
                "first_name": "Marie-Claire",
                "last_name": "Dupont",
                "phone": "0470 12 34 56",
                "birth_date": "1955-04-21",
            },
        )

        self.assertRedirects(response, reverse("client_list"))
        self.marie.refresh_from_db()
        self.assertEqual(self.marie.first_name, "Marie-Claire")
        self.assertEqual(self.marie.phone, "0470123456")
        self.assertEqual(self.marie.birth_date, date(1955, 4, 21))

    def test_email_and_password_not_editable(self):
        self.client.post(
            self.url,
            {
                "first_name": "Marie",
                "last_name": "Dupont",
                "birth_date": "1955-04-12",
                "email": "pirate@example.com",
                "password": "nouveau-mdp-2026",
                "role": Role.ADMINISTRATOR,
            },
        )

        self.marie.refresh_from_db()
        self.assertEqual(self.marie.email, "client@example.com")
        self.assertTrue(self.marie.check_password(PASSWORD))
        self.assertEqual(self.marie.role, Role.CLIENT)

    def test_invalid_data_rejected(self):
        response = self.client.post(
            self.url, {"first_name": "Marie", "last_name": "Dupont", "phone": "123", "birth_date": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.marie.refresh_from_db()
        self.assertEqual(self.marie.phone, "")


class ClientPasswordLinkTests(SendEmailsImmediately, TestCase):
    def test_send_link_to_client(self):
        self.client.force_login(create_agent())
        client = create_client()

        response = self.client.post(reverse("send_client_link", args=[client.pk]))

        self.assertRedirects(response, reverse("edit_client", args=[client.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["client@example.com"])

        # Le client suit le lien et choisit lui-même son mot de passe.
        self.client.logout()
        link = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
        form_page = self.client.get(link, follow=True)
        self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": "montagne-lac-77", "new_password2": "montagne-lac-77"},
        )
        client.refresh_from_db()
        self.assertTrue(client.check_password("montagne-lac-77"))

    def test_get_denied(self):
        self.client.force_login(create_agent())
        client = create_client()

        self.assertEqual(
            self.client.get(reverse("send_client_link", args=[client.pk])).status_code, 405
        )

    @mock.patch("accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur SMTP injoignable"))
    def test_email_failure_is_reported(self, _send_mail):
        self.client.force_login(create_agent())
        client = create_client()

        with self.assertLogs("accounts.services.emails", level="ERROR") as logs:
            response = self.client.post(reverse("send_client_link", args=[client.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "n&#x27;a pas pu être envoyé")
        self.assertIn("serveur SMTP injoignable", logs.output[0])
