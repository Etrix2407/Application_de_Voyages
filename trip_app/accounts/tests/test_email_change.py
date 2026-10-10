import re
from unittest import mock

from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.services.email_change import apply_email_change

from .factories import PASSWORD, create_agent, create_client


class EmailChangeTests(TestCase):
    url = reverse("change_email")

    def setUp(self):
        cache.clear()
        self.user = create_client()
        self.client.force_login(self.user)

    def request_change(self, new_email="nouvelle@example.com", password=PASSWORD):
        return self.client.post(self.url, {"new_email": new_email, "password": password}, follow=True)

    def link_sent_to(self, address):
        message = next(m for m in mail.outbox if m.to == [address])
        return re.search(r"https?://[^/]+(/\S+)", message.body).group(1)

    def test_profile_offers_the_change(self):
        self.assertContains(self.client.get(reverse("profile")), self.url)

    def test_password_required(self):
        response = self.request_change(password="mauvais-mot-2026")

        self.assertContains(response, "Mot de passe incorrect.")
        self.assertEqual(len(mail.outbox), 0)

    def test_change_applied_only_after_clicking_the_link(self):
        response = self.request_change("Nouvelle@Example.com")

        self.assertContains(response, "Votre adresse ne changera qu")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "client@example.com")
        # L'ancienne adresse est prévenue.
        self.assertTrue(any(m.to == ["client@example.com"] for m in mail.outbox))

        link = self.link_sent_to("nouvelle@example.com")
        page = self.client.get(link)
        self.assertContains(page, "nouvelle@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "client@example.com")  # ouvrir le lien ne change rien

        response = self.client.post(link, follow=True)

        self.assertContains(response, "Votre adresse e-mail est maintenant nouvelle@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nouvelle@example.com")

    def test_taken_address_not_revealed(self):
        create_client(email="pris@example.com")

        taken = self.request_change("pris@example.com")
        free = self.request_change("libre@example.com")

        # Message identique, aucune mention « existe déjà » ; aucun lien envoyé à l'adresse prise.
        for response in (taken, free):
            self.assertContains(response, "Si cette adresse peut être utilisée")
            self.assertNotContains(response, "existe déjà")
        self.assertFalse(any(m.to == ["pris@example.com"] for m in mail.outbox))

    def test_same_address_refused(self):
        self.assertContains(self.request_change("CLIENT@example.com"), "déjà votre adresse actuelle")

    def test_link_unusable_if_address_taken_meanwhile(self):
        self.request_change("nouvelle@example.com")
        link = self.link_sent_to("nouvelle@example.com")
        create_client(email="nouvelle@example.com")

        response = self.client.get(link)

        self.assertContains(response, "plus valable")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "client@example.com")

    def test_address_taken_while_confirming_shows_same_page(self):
        self.request_change("nouvelle@example.com")
        link = self.link_sent_to("nouvelle@example.com")

        def taken_then_apply(*args, **kwargs):
            # Un autre compte prend l'adresse entre la vérification du lien et l'enregistrement.
            create_client(email="nouvelle@example.com")
            return apply_email_change(*args, **kwargs)

        with mock.patch("accounts.views.profile.apply_email_change", side_effect=taken_then_apply):
            response = self.client.post(link)

        self.assertContains(response, "plus valable")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "client@example.com")

    def test_older_link_unusable_after_another_change(self):
        self.request_change("premiere@example.com")
        first_link = self.link_sent_to("premiere@example.com")
        self.request_change("seconde@example.com")
        self.client.post(self.link_sent_to("seconde@example.com"))

        self.assertContains(self.client.get(first_link), "plus valable")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "seconde@example.com")

    def test_tampered_link_refused(self):
        self.request_change()

        self.assertContains(self.client.get(self.link_sent_to("nouvelle@example.com")[:-4] + "xyz/"), "plus valable")

    def test_link_works_from_another_device(self):
        self.request_change()
        link = self.link_sent_to("nouvelle@example.com")
        self.client.logout()

        response = self.client.post(link, follow=True)

        self.assertRedirects(response, reverse("login"))
        self.assertTrue(User.objects.filter(email="nouvelle@example.com").exists())

    def test_link_for_a_staff_account_refused(self):
        # Même un lien correctement signé ne change jamais l'adresse d'un membre du personnel.
        agent = create_agent()
        token = signing.dumps(
            {"id": agent.pk, "old": agent.email, "new": "pirate@example.com"}, salt="accounts.email-change"
        )
        url = reverse("confirm_email_change", args=[token])

        self.assertContains(self.client.post(url), "plus valable")
        agent.refresh_from_db()
        self.assertNotEqual(agent.email, "pirate@example.com")
