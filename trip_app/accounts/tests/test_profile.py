from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.forms import ClientCorrectionForm
from accounts.models import Role

from .email_delivery import SendEmailsImmediately
from .factories import PASSWORD, create_admin, create_agent, create_client

User = get_user_model()


class ProfileViewTests(TestCase):
    def test_client_sees_own_information_not_others(self):
        client = create_client(phone="0470123456")
        create_client(email="voisin@example.com", last_name="Voisin")
        self.client.force_login(client)

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "client@example.com")
        self.assertContains(response, "0470123456")
        self.assertContains(response, reverse("delete_account"))
        self.assertNotContains(response, "voisin@example.com")

    def test_agent_sees_number_without_delete_link(self):
        agent = create_agent()
        self.client.force_login(agent)

        response = self.client.get(reverse("profile"))

        self.assertContains(response, "AG0001")
        self.assertContains(response, reverse("change_password"))
        self.assertNotContains(response, reverse("delete_account"))
        self.assertNotContains(response, reverse("edit_profile"))


class ProfileEditTests(TestCase):
    url = reverse("edit_profile")

    def setUp(self):
        self.user = create_client()
        self.client.force_login(self.user)

    def data(self, **fields):
        data = {
            "first_name": "Marie",
            "last_name": "Durand",
            "email": "Nouvelle@Example.com",
            "phone": "+32 2 123 45 67",
            "birth_date": "1956-05-01",
        }
        data.update(fields)
        return data

    def test_change_saved(self):
        response = self.client.post(self.url, self.data())

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, "Durand")
        self.assertEqual(self.user.phone, "+3221234567")
        self.assertEqual(self.user.birth_date, date(1956, 5, 1))

    def test_email_cannot_be_changed_from_this_form(self):
        # Audit : l'e-mail se change à part, avec mot de passe et lien de confirmation.
        self.client.post(self.url, self.data(email="pirate@example.com"))

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "client@example.com")
        self.assertNotIn("email", self.client.get(self.url).context["form"].fields)

    def test_role_not_editable(self):
        self.client.post(self.url, self.data(role=Role.ADMINISTRATOR))

        self.user.refresh_from_db()
        self.assertEqual(self.user.role, Role.CLIENT)

    def test_promotional_emails_consent_given_kept_then_withdrawn(self):
        self.client.post(self.url, self.data(promotional_emails="on"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.accepts_promotional_emails)
        consent_date = self.user.promotional_emails_choice_date
        self.assertIsNotNone(consent_date)

        # Réenregistrer sans toucher à la case garde la date d'origine (preuve du consentement).
        self.assertTrue(self.client.get(self.url).context["form"]["promotional_emails"].value())
        self.client.post(self.url, self.data(last_name="Martin", promotional_emails="on"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.promotional_emails_choice_date, consent_date)

        # Le retrait est daté lui aussi : la trace du changement est gardée.
        self.client.post(self.url, self.data())
        self.user.refresh_from_db()
        self.assertFalse(self.user.accepts_promotional_emails)
        self.assertGreater(self.user.promotional_emails_choice_date, consent_date)

    def test_agent_correction_cannot_change_promotional_emails_consent(self):
        self.assertNotIn("promotional_emails", ClientCorrectionForm().fields)

    def test_birth_date_required(self):
        response = self.client.post(self.url, self.data(birth_date=""))

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.birth_date, date(1955, 4, 12))


class PasswordChangeTests(SendEmailsImmediately, TestCase):
    url = reverse("change_password")

    def change_password(self, old_password, new_password="montagne-lac-77"):
        return self.client.post(
            self.url,
            {"old_password": old_password, "new_password1": new_password, "new_password2": new_password},
        )

    def test_change_keeps_session(self):
        client = create_client()
        self.client.force_login(client)

        response = self.change_password(PASSWORD)

        self.assertRedirects(response, reverse("profile"))
        client.refresh_from_db()
        self.assertTrue(client.check_password("montagne-lac-77"))
        self.assertEqual(self.client.get(reverse("profile")).status_code, 200)

    def test_old_password_required(self):
        client = create_client()
        self.client.force_login(client)

        response = self.change_password("mauvais-mot-2026")

        self.assertEqual(response.status_code, 200)
        client.refresh_from_db()
        self.assertTrue(client.check_password(PASSWORD))

    def test_strong_new_password_required(self):
        client = create_client()
        self.client.force_login(client)

        self.change_password(PASSWORD, new_password="court")

        client.refresh_from_db()
        self.assertTrue(client.check_password(PASSWORD))

    def test_agent_can_change_own_password(self):
        agent = create_agent()
        self.client.force_login(agent)

        self.assertRedirects(self.change_password(PASSWORD), reverse("profile"))

    def test_security_email_sent_to_clients_and_staff(self):
        for user in [create_client(), create_agent(), create_admin()]:
            with self.subTest(role=user.role):
                mail.outbox.clear()
                self.client.force_login(user)

                self.change_password(PASSWORD)

                self.assertEqual(
                    [(message.to, message.subject) for message in mail.outbox],
                    [([user.email], "Votre mot de passe a été modifié")],
                )


class AccountDeletionTests(TestCase):
    url = reverse("delete_account")

    def setUp(self):
        self.user = create_client()
        self.client.force_login(self.user)

    def test_wrong_password_deletes_nothing(self):
        response = self.client.post(self.url, {"password": "mauvais-mot-2026"})

        self.assertContains(response, "Mot de passe incorrect.")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_permanent_deletion_and_logout(self):
        response = self.client.post(self.url, {"password": PASSWORD}, follow=True)

        self.assertRedirects(response, reverse("home"))
        self.assertContains(response, "Votre compte et vos données ont été supprimés.")
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)
