import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts import throttling
from accounts.models import Role

from .factories import PASSWORD, create_client

User = get_user_model()


def sign_up_data(**fields):
    data = {
        "first_name": "Marie",
        "last_name": "Dupont",
        "email": "marie@example.com",
        "phone": "0470 12 34 56",
        "birth_date": "1955-04-12",
        "password1": "soleil-plage-42",
        "password2": "soleil-plage-42",
        "consent": "on",
    }
    data.update(fields)
    return data


class SignUpTests(TestCase):
    url = reverse("sign_up")

    def test_page_accessible(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "politique de confidentialité")

    def test_sign_up_creates_logged_in_client(self):
        response = self.client.post(self.url, sign_up_data())

        self.assertRedirects(response, reverse("home"))
        client = User.objects.get(email="marie@example.com")
        self.assertEqual(client.role, Role.CLIENT)
        self.assertEqual(client.phone, "0470123456")
        self.assertIsNotNone(client.consent_date)
        self.assertTrue(client.check_password("soleil-plage-42"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), client.pk)

    def test_role_forced_even_if_sent(self):
        self.client.post(self.url, sign_up_data(role=Role.ADMINISTRATOR))

        self.assertEqual(User.objects.get().role, Role.CLIENT)

    def test_sign_up_rejected(self):
        cases = {
            "sans consentement": {"consent": ""},
            "sans date de naissance": {"birth_date": ""},
            "mot de passe faible": {"password1": "court", "password2": "court"},
            "mots de passe différents": {"password2": "autre-chose-42"},
            "téléphone étranger": {"phone": "+33 6 12 34 56 78"},
        }
        for reason, fields in cases.items():
            with self.subTest(reason=reason):
                response = self.client.post(self.url, sign_up_data(**fields))

                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())

    def test_email_already_used_whatever_the_case(self):
        create_client(email="marie@example.com")

        response = self.client.post(self.url, sign_up_data(email="MARIE@example.com"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 1)

    def test_logged_in_user_redirected(self):
        self.client.force_login(create_client())

        self.assertRedirects(self.client.get(self.url), reverse("home"))


class LoginTests(TestCase):
    url = reverse("login")

    def setUp(self):
        cache.clear()
        self.user = create_client()

    def log_in(self, email="client@example.com", password=PASSWORD):
        return self.client.post(self.url, {"username": email, "password": password})

    def test_successful_login(self):
        response = self.log_in()

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_case_insensitive(self):
        self.assertRedirects(self.log_in(email="Client@Example.com"), reverse("home"))

    def test_wrong_password(self):
        response = self.log_in(password="mauvais-mot-2026")

        self.assertContains(response, "Adresse e-mail ou mot de passe incorrect.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_account_denied(self):
        self.user.is_active = False
        self.user.save()

        response = self.log_in()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_locked_after_too_many_failures(self):
        for _ in range(throttling.MAX_FAILURES):
            self.log_in(password="mauvais-mot-2026")

        response = self.log_in()

        self.assertContains(response, "Trop de tentatives échouées")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lockout_is_per_email(self):
        for _ in range(throttling.MAX_FAILURES):
            self.log_in(email="autre@example.com", password="mauvais-mot-2026")

        self.assertRedirects(self.log_in(), reverse("home"))

    def test_success_resets_counter(self):
        for _ in range(throttling.MAX_FAILURES - 1):
            self.log_in(password="mauvais-mot-2026")
        self.log_in()
        self.client.logout()

        self.log_in(password="mauvais-mot-2026")

        self.assertFalse(throttling.is_locked("client@example.com"))

    def test_logout(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    url = reverse("password_reset")

    def test_link_valid_one_hour(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    def test_email_sent_and_link_works(self):
        client = create_client()

        response = self.client.post(self.url, {"email": "CLIENT@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)

        # Django remplace le jeton par un jeton de session puis redirige.
        form_page = self.client.get(link, follow=True)
        self.assertTrue(form_page.context["validlink"])
        new_password = "montagne-lac-77"
        response = self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": new_password, "new_password2": new_password},
        )

        self.assertRedirects(response, reverse("password_reset_complete"))
        client.refresh_from_db()
        self.assertTrue(client.check_password(new_password))

    def test_unknown_email_neutral_message(self):
        response = self.client.post(self.url, {"email": "inconnu@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class PrivacyTests(TestCase):
    def test_page_accessible_and_linked_in_footer(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("privacy")}"')
