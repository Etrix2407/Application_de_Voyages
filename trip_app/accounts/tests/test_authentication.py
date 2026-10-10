import importlib
import re
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.apps import apps as django_apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.sign_up import purge_unconfirmed
from accounts.services.throttling import confirmation_emails, login_failures, password_reset_requests
from accounts.models import EmailLog, Role

from .email_delivery import SendEmailsImmediately
from .factories import PASSWORD, create_agent, create_client

User = get_user_model()

NEW_PASSWORD = "soleil-plage-42"


def sign_up_data(**fields):
    data = {
        "first_name": "Marie",
        "last_name": "Dupont",
        "email": "marie@example.com",
        "phone": "0470 12 34 56",
        "birth_date": "1955-04-12",
        "password1": NEW_PASSWORD,
        "password2": NEW_PASSWORD,
        "consent": "on",
    }
    data.update(fields)
    return data


def link_in_last_email() -> str:
    return re.search(r"https?://[^/]+(/\S+)", mail.outbox[-1].body).group(1)


class SignUpTests(SendEmailsImmediately, TestCase):
    url = reverse("sign_up")

    def setUp(self):
        cache.clear()

    def test_page_accessible(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "politique de confidentialité")
        self.assertContains(response, 'type="password"')

    def test_sign_up_creates_unconfirmed_client_with_password_and_sends_link(self):
        response = self.client.post(self.url, sign_up_data())

        self.assertRedirects(response, reverse("sign_up_done"))
        user = User.objects.get(email="marie@example.com")
        self.assertEqual(user.role, Role.CLIENT)
        self.assertTrue(user.is_awaiting_confirmation)
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertIsNotNone(user.consent_date)
        self.assertEqual(user.phone, "0470123456")
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])
        self.assertIn("48 heures", mail.outbox[-1].body)

    def test_promotional_emails_box_unchecked_by_default(self):
        response = self.client.get(self.url)

        self.assertFalse(response.context["form"]["promotional_emails"].value())
        self.assertInHTML(
            '<input type="checkbox" name="promotional_emails" id="id_promotional_emails">',
            response.content.decode(),
        )

    def test_promotional_emails_consent_recorded_only_if_box_checked(self):
        self.client.post(self.url, sign_up_data())
        self.client.post(self.url, sign_up_data(email="julie@example.com", promotional_emails="on"))

        without = User.objects.get(email="marie@example.com")
        self.assertFalse(without.accepts_promotional_emails)
        self.assertIsNone(without.promotional_emails_choice_date)
        with_consent = User.objects.get(email="julie@example.com")
        self.assertTrue(with_consent.accepts_promotional_emails)
        self.assertIsNotNone(with_consent.promotional_emails_choice_date)

    def test_can_log_in_before_confirmation(self):
        self.client.post(self.url, sign_up_data())

        response = self.client.post(reverse("login"), {"username": "marie@example.com", "password": NEW_PASSWORD})

        self.assertRedirects(response, reverse("home"))

    def test_three_login_failures_after_sign_up_lock_the_ip(self):
        # Freine le test d'adresses : s'inscrire puis essayer de se connecter avec le mot de passe choisi.
        create_client(email="autre@example.com")
        self.client.post(self.url, sign_up_data())
        for address in ["a@example.com", "b@example.com", "c@example.com"]:
            self.client.post(reverse("login"), {"username": address, "password": NEW_PASSWORD})

        response = self.client.post(reverse("login"), {"username": "autre@example.com", "password": PASSWORD})

        self.assertContains(response, "Trop de tentatives échouées")

    def test_weak_password_refused(self):
        response = self.client.post(self.url, sign_up_data(password1="court", password2="court"))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_existing_address_not_revealed(self):
        create_client(email="marie@example.com")

        response = self.client.post(self.url, sign_up_data(email="MARIE@example.com"))

        # Même page qu'une inscription nouvelle ; aucun second compte.
        self.assertRedirects(response, reverse("sign_up_done"))
        self.assertEqual(User.objects.count(), 1)
        # La vraie propriétaire de l'adresse est prévenue.
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])
        self.assertIn("Un compte existe déjà", mail.outbox[-1].body)

    def test_new_sign_up_replaces_unconfirmed_account(self):
        # Un tiers inscrit l'adresse de Marie avec son propre mot de passe.
        pirate_password = "tiers-connu-2026"
        self.client.post(
            self.url, sign_up_data(first_name="Pirate", password1=pirate_password, password2=pirate_password)
        )
        pirate_link = link_in_last_email()
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=1)):
            self.client.post(self.url, sign_up_data())

        user = User.objects.get(email="marie@example.com")
        self.assertEqual(user.first_name, "Marie")
        self.assertFalse(user.check_password(pirate_password))
        # Le lien envoyé pour le compte remplacé ne vaut plus rien.
        self.assertContains(self.client.get(pirate_link), "plus valable")

    def test_role_forced_even_if_sent(self):
        self.client.post(self.url, sign_up_data(role=Role.ADMINISTRATOR))

        self.assertEqual(User.objects.get().role, Role.CLIENT)

    def test_sign_up_rejected(self):
        cases = {
            "sans consentement": {"consent": ""},
            "sans date de naissance": {"birth_date": ""},
            "téléphone invalide": {"phone": "12345"},
            "mots de passe différents": {"password2": "autre-mot-2026"},
        }
        for reason, fields in cases.items():
            with self.subTest(reason=reason):
                response = self.client.post(self.url, sign_up_data(**fields))

                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())

    def test_logged_in_user_redirected(self):
        self.client.force_login(create_client())

        self.assertRedirects(self.client.get(self.url), reverse("home"))


class ConfirmationLinkTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        cache.clear()
        self.client.post(reverse("sign_up"), sign_up_data(first_name="Pirate"))
        self.link = link_in_last_email()

    def test_page_shows_account_data_and_confirms_only_on_click(self):
        page = self.client.get(self.link)

        # La propriétaire de l'adresse voit si ce compte est le sien avant de confirmer.
        self.assertContains(page, "Pirate Dupont")
        self.assertContains(page, "0470123456")
        self.assertContains(page, "12 avril 1955")
        self.assertContains(page, "recommencez l'inscription")
        self.assertTrue(User.objects.get().is_awaiting_confirmation)

        response = self.client.post(self.link)

        self.assertRedirects(response, reverse("login"))
        self.assertFalse(User.objects.get().is_awaiting_confirmation)

    def test_link_valid_48_hours(self):
        now = timezone.now().timestamp()
        with mock.patch("django.core.signing.time") as clock:
            clock.time.return_value = now + 47 * 3600
            self.assertContains(self.client.get(self.link), "Confirmer mon adresse")
            clock.time.return_value = now + 49 * 3600
            self.assertContains(self.client.get(self.link), "plus valable")

    def test_tampered_link_refused(self):
        response = self.client.get(self.link[:-3] + "xyz/")

        self.assertContains(response, "plus valable")

    def test_already_confirmed_redirects_to_login(self):
        self.client.post(self.link)

        self.assertRedirects(self.client.get(self.link), reverse("login"))

    def test_resend_link_only_for_unconfirmed_address(self):
        create_client(email="active@example.com")
        sent = len(mail.outbox)

        for email in ["marie@example.com", "active@example.com", "inconnu@example.com"]:
            response = self.client.post(reverse("resend_confirmation"), {"email": email})
            # Réponse identique dans tous les cas.
            self.assertRedirects(response, reverse("sign_up_done"))

        self.assertEqual(len(mail.outbox), sent + 1)
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])

    def test_logged_in_client_resends_link_from_profile(self):
        user = User.objects.get()
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse("profile")), reverse("resend_confirmation"))

        response = self.client.post(reverse("resend_confirmation"))

        self.assertRedirects(response, reverse("profile"))
        self.assertEqual(mail.outbox[-1].to, ["marie@example.com"])
        self.client.post(link_in_last_email())
        self.assertFalse(User.objects.get().is_awaiting_confirmation)

    def test_confirmation_emails_limited_per_address(self):
        for _ in range(10):
            self.client.post(reverse("resend_confirmation"), {"email": "marie@example.com"})

        self.assertEqual(len(mail.outbox), confirmation_emails.max_attempts)


class DeletePendingSignUpsBeforeV5Tests(TestCase):
    """Migration 0008 : seules les inscriptions clients d'avant la v5 sont supprimées."""

    def test_only_old_pending_client_sign_ups_deleted(self):
        migration = importlib.import_module("accounts.migrations.0008_delete_pending_sign_ups_before_v5")
        # Avant la v5 : compte inactif, sans mot de passe utilisable.
        old_pending = create_client(email="ancien@example.com", is_active=False, email_confirmed_at=None)
        invited_agent = create_agent(email="invite@example.com")
        deactivated_agent = create_agent(email="parti@example.com", is_active=False)
        for user in (old_pending, invited_agent, deactivated_agent):
            user.set_unusable_password()
            user.save()
        new_unconfirmed = create_client(email="nouveau@example.com", email_confirmed_at=None)

        migration.delete_pending_sign_ups(django_apps, None)

        self.assertEqual(set(User.objects.all()), {invited_agent, deactivated_agent, new_unconfirmed})


class PurgeUnconfirmedTests(TestCase):
    def test_accounts_unconfirmed_after_30_days_deleted(self):
        cache.clear()
        self.client.post(reverse("sign_up"), sign_up_data())
        confirmed = create_client(email="active@example.com")

        self.assertEqual(purge_unconfirmed(now=timezone.now() + timedelta(days=29)), 0)
        self.assertEqual(purge_unconfirmed(now=timezone.now() + timedelta(days=31)), 1)

        self.assertEqual(list(User.objects.all()), [confirmed])


class PurgeUnconfirmedEmailTests(TransactionTestCase):
    """Commande planifiée, hors requête et sans transaction de test : l'e-mail part vraiment après validation."""

    def test_purged_account_receives_last_email(self):
        create_client(
            email="jamais@example.com", email_confirmed_at=None, date_joined=timezone.now() - timedelta(days=31)
        )

        call_command("purge_unconfirmed", stdout=StringIO())

        self.assertFalse(User.objects.exists())
        self.assertEqual(
            [(message.to, message.subject) for message in mail.outbox],
            [(["jamais@example.com"], "Votre compte a été supprimé")],
        )
        self.assertIn("jamais été confirmée", mail.outbox[0].body)
        self.assertEqual(EmailLog.objects.get().recipient, "")


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


class PasswordResetTests(SendEmailsImmediately, TestCase):
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
        # Alerte de sécurité « mot de passe modifié ».
        self.assertEqual(
            (len(mail.outbox), mail.outbox[-1].to, mail.outbox[-1].subject),
            (2, ["client@example.com"], "Votre mot de passe a été modifié"),
        )

    def test_unknown_email_neutral_message(self):
        response = self.client.post(self.url, {"email": "inconnu@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class PrivacyTests(TestCase):
    def test_page_accessible_and_linked_in_footer(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{reverse("privacy")}"')

    def test_no_placeholder_left_and_contact_given(self):
        response = self.client.get(reverse("privacy"))

        self.assertNotContains(response, "COMPLÉTER")
        self.assertContains(response, "mailto:")
        self.assertContains(response, "Durée de conservation")
