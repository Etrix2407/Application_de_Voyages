import re
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.sign_up import UNCONFIRMED_RETENTION, purge_unconfirmed
from accounts.services.throttling import confirmation_emails, login_failures, password_reset_requests
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
        "consent": "on",
    }
    data.update(fields)
    return data


def link_in_last_email() -> str:
    return re.search(r"https?://[^/]+(/\S+)", mail.outbox[-1].body).group(1)


class SignUpTests(TestCase):
    url = reverse("sign_up")

    def setUp(self):
        cache.clear()

    def test_page_accessible(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "politique de confidentialité")
        self.assertNotContains(response, 'type="password"')

    def test_sign_up_creates_inactive_client_and_sends_link(self):
        response = self.client.post(self.url, sign_up_data())

        self.assertRedirects(response, reverse("sign_up_done"))
        user = User.objects.get(email="marie@example.com")
        self.assertEqual(user.role, Role.CLIENT)
        self.assertFalse(user.is_active)
        self.assertTrue(user.is_awaiting_confirmation)
        self.assertFalse(user.has_usable_password())
        self.assertIsNotNone(user.consent_date)
        self.assertEqual(user.phone, "0470123456")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])

    def test_link_lets_user_choose_password_and_activates_account(self):
        self.client.post(self.url, sign_up_data())

        page = self.client.get(link_in_last_email())
        self.assertContains(page, "Bienvenue Marie")
        response = self.client.post(
            link_in_last_email(), {"new_password1": "soleil-plage-42", "new_password2": "soleil-plage-42"}
        )

        self.assertRedirects(response, reverse("home"))
        user = User.objects.get(email="marie@example.com")
        self.assertTrue(user.is_active)
        self.assertIsNotNone(user.email_confirmed_at)
        self.assertTrue(user.check_password("soleil-plage-42"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_weak_password_refused_at_confirmation(self):
        self.client.post(self.url, sign_up_data())

        response = self.client.post(link_in_last_email(), {"new_password1": "court", "new_password2": "court"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.get(email="marie@example.com").is_active)

    def test_existing_address_not_revealed(self):
        create_client(email="marie@example.com")

        response = self.client.post(self.url, sign_up_data(email="MARIE@example.com"))

        # Même page qu'une inscription nouvelle ; aucun second compte.
        self.assertRedirects(response, reverse("sign_up_done"))
        self.assertEqual(User.objects.count(), 1)
        # La vraie propriétaire de l'adresse est prévenue.
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])
        self.assertIn("Un compte existe déjà", mail.outbox[-1].body)

    def test_account_pre_hijacking_impossible(self):
        # Un pirate s'inscrit avec l'adresse de Marie : il ne choisit aucun mot de passe.
        self.client.post(self.url, sign_up_data(first_name="Pirate"))
        user = User.objects.get(email="marie@example.com")
        self.assertFalse(user.has_usable_password())
        # Seule la personne qui reçoit l'e-mail choisit le mot de passe.
        self.client.post(
            link_in_last_email(), {"new_password1": "montagne-lac-77", "new_password2": "montagne-lac-77"}
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password("montagne-lac-77"))

    def test_new_attempt_replaces_pending_sign_up(self):
        self.client.post(self.url, sign_up_data(first_name="Erreur"))

        self.client.post(self.url, sign_up_data(first_name="Marie"))

        self.assertEqual(User.objects.get(email="marie@example.com").first_name, "Marie")

    def test_role_forced_even_if_sent(self):
        self.client.post(self.url, sign_up_data(role=Role.ADMINISTRATOR))

        self.assertEqual(User.objects.get().role, Role.CLIENT)

    def test_sign_up_rejected(self):
        cases = {
            "sans consentement": {"consent": ""},
            "sans date de naissance": {"birth_date": ""},
            "téléphone invalide": {"phone": "12345"},
        }
        for reason, fields in cases.items():
            with self.subTest(reason=reason):
                response = self.client.post(self.url, sign_up_data(**fields))

                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())

    def test_logged_in_user_redirected(self):
        self.client.force_login(create_client())

        self.assertRedirects(self.client.get(self.url), reverse("home"))


class ConfirmationLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client.post(reverse("sign_up"), sign_up_data())
        self.link = link_in_last_email()

    def test_tampered_link_refused(self):
        response = self.client.get(self.link[:-3] + "xyz/")

        self.assertContains(response, "plus valable")

    def test_expired_link_refused(self):
        with mock.patch("accounts.services.sign_up.CONFIRMATION_MAX_AGE", timedelta(seconds=-1)):
            response = self.client.get(self.link)

        self.assertContains(response, "plus valable")

    def test_already_confirmed_redirects_to_login(self):
        self.client.post(self.link, {"new_password1": "soleil-plage-42", "new_password2": "soleil-plage-42"})
        self.client.logout()

        self.assertRedirects(self.client.get(self.link), reverse("login"))

    def test_resend_link_only_for_pending_sign_up(self):
        create_client(email="active@example.com")
        sent = len(mail.outbox)

        for email in ["marie@example.com", "active@example.com", "inconnu@example.com"]:
            response = self.client.post(reverse("resend_confirmation"), {"email": email})
            # Réponse identique dans tous les cas.
            self.assertRedirects(response, reverse("sign_up_done"))

        self.assertEqual(len(mail.outbox), sent + 1)
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])

    def test_confirmation_emails_limited_per_address(self):
        for _ in range(10):
            self.client.post(reverse("resend_confirmation"), {"email": "marie@example.com"})

        self.assertEqual(len(mail.outbox), confirmation_emails.max_attempts)


class PurgeUnconfirmedTests(TestCase):
    def test_old_unconfirmed_sign_ups_deleted(self):
        cache.clear()
        self.client.post(reverse("sign_up"), sign_up_data())
        active = create_client(email="active@example.com")
        later = timezone.now() + UNCONFIRMED_RETENTION + timedelta(minutes=1)

        self.assertEqual(purge_unconfirmed(now=timezone.now()), 0)
        self.assertEqual(purge_unconfirmed(now=later), 1)

        self.assertEqual(list(User.objects.all()), [active])


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
        for _ in range(login_failures.max_attempts):
            self.log_in(password="mauvais-mot-2026")

        response = self.log_in()

        self.assertContains(response, "Trop de tentatives échouées")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lockout_is_per_email(self):
        for _ in range(login_failures.max_attempts):
            self.log_in(email="autre@example.com", password="mauvais-mot-2026")

        self.assertRedirects(self.log_in(), reverse("home"))

    def test_success_resets_counter(self):
        for _ in range(login_failures.max_attempts - 1):
            self.log_in(password="mauvais-mot-2026")
        self.log_in()
        self.client.logout()

        self.log_in(password="mauvais-mot-2026")

        self.assertFalse(login_failures.is_locked("client@example.com"))

    def test_logout(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PasswordResetTests(TestCase):
    url = reverse("password_reset")

    def setUp(self):
        cache.clear()

    def test_requests_limited_per_address(self):
        create_client(email="victime@example.com")
        limit = password_reset_requests.max_attempts

        for _ in range(limit + 5):
            response = self.client.post(self.url, {"email": "victime@example.com"})
            # La page reste identique : rien ne révèle que la limite est atteinte.
            self.assertRedirects(response, reverse("password_reset_done"))

        self.assertEqual(len(mail.outbox), limit)

    def test_limit_is_per_address(self):
        create_client(email="victime@example.com")
        create_client(email="autre@example.com")
        for _ in range(password_reset_requests.max_attempts):
            self.client.post(self.url, {"email": "victime@example.com"})

        self.client.post(self.url, {"email": "AUTRE@example.com"})

        self.assertEqual(mail.outbox[-1].to, ["autre@example.com"])

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
