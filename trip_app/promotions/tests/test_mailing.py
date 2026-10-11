from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse, reverse_lazy
from django.utils import timezone

from accounts.models import AccountEmail, EmailLog, EmailStatus
from accounts.services.email_retry import OBSOLETE, retry_due_emails
from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.tests.factories import create_order
from promotions.models import PromotionEmail, PromotionMailing, Scope
from promotions.services.mailing import send_promotion_mailing
from promotions.tests.factories import create_promotion


MAILING_URL = reverse_lazy("manage_send_promotion_mailing")


def confirmed_mailing(client, data: dict) -> dict:
    """Données de l'envoi réel : celles du formulaire, avec le jeton de la page de confirmation."""
    confirmation = client.post(MAILING_URL, data)
    return {**data, "submission_token": confirmation.context["submission_token"], "confirm": ""}


class MailingPageTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin(first_name="Anne", last_name="Durand"))
        self.promotion = create_promotion(code="SOLEIL10")
        self.url = MAILING_URL
        self.data = {"promotion": self.promotion.pk, "message": "Le printemps arrive !"}

    def test_confirmation_shows_recipients_and_preview_before_sending(self):
        create_client("marie@example.com", accepts_promotional_emails=True)

        response = self.client.post(self.url, self.data)

        self.assertContains(response, "à 1 client ?")
        self.assertContains(response, "Bonjour Marie")
        self.assertContains(response, "Le printemps arrive !")
        self.assertContains(response, "SOLEIL10")
        self.assertFalse(PromotionMailing.objects.exists())

    def test_sent_once_despite_a_double_click(self):
        create_client("marie@example.com", accepts_promotional_emails=True)
        data = confirmed_mailing(self.client, self.data)

        self.client.post(self.url, data)
        response = self.client.post(self.url, data, follow=True)

        self.assertContains(response, "avait déjà été programmé")
        self.assertEqual(PromotionMailing.objects.count(), 1)
        self.assertEqual(EmailLog.objects.count(), 1)

    def test_no_send_button_without_recipients(self):
        response = self.client.get(self.url)

        self.assertContains(response, "l'envoi n'est pas possible")
        self.assertNotContains(response, "Vérifier avant l'envoi")

    def test_queued_only_for_promotion_recipients(self):
        marie = create_client("marie@example.com", accepts_promotional_emails=True)
        create_client("sans.accord@example.com")
        create_client("non.confirmee@example.com", accepts_promotional_emails=True, email_confirmed_at=None)
        create_client("inactive@example.com", accepts_promotional_emails=True, is_active=False)

        response = self.client.post(self.url, confirmed_mailing(self.client, self.data), follow=True)

        self.assertContains(response, "L&#x27;envoi à 1 client a été programmé")
        mailing = PromotionMailing.objects.get()
        self.assertEqual((mailing.recipients_count, mailing.author_name), (1, "Anne Durand"))
        log = EmailLog.objects.get()
        self.assertEqual(
            (log.user, log.kind, log.status, log.attempts), (marie, PromotionEmail.PROMOTION, EmailStatus.PENDING, 0)
        )
        self.assertEqual(log.promotion_mailing_number, mailing.pk)
        self.assertEqual(mail.outbox, [])  # rien n'est envoyé pendant la requête
        self.assertContains(response, "envoyée par Anne Durand")  # envoi listé sur la fiche de la promotion

    def test_refused_without_recipients(self):
        response = self.client.post(self.url, confirmed_mailing(self.client, self.data), follow=True)

        self.assertContains(response, "rien n&#x27;a été envoyé")
        self.assertFalse(PromotionMailing.objects.exists())
        self.assertFalse(EmailLog.objects.exists())

    def test_agents_cannot_send(self):
        create_client(accepts_promotional_emails=True)
        self.client.force_login(create_agent())

        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        self.assertFalse(EmailLog.objects.exists())


class PromotionEmailTests(TestCase):
    def setUp(self):
        self.marie = create_client("marie@example.com", accepts_promotional_emails=True)
        self.client.force_login(create_admin())
        data = {"promotion": create_promotion(code="SOLEIL10").pk, "message": "Le printemps arrive !"}
        self.client.post(MAILING_URL, confirmed_mailing(self.client, data))
        self.log = EmailLog.objects.get()

    def test_sent_on_next_run_with_unsubscribe_link(self):
        self.assertEqual(retry_due_emails(), 1)

        self.log.refresh_from_db()
        self.assertEqual(self.log.status, EmailStatus.SENT)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["marie@example.com"])
        self.assertIn("Bonjour Marie", message.body)
        self.assertIn("Le printemps arrive !", message.body)
        self.assertIn("SOLEIL10", message.body)
        self.assertRegex(message.body, r"/comptes/desinscription/[\w:-]+/")
        self.assertRegex(message.extra_headers["List-Unsubscribe"], r"^<http.+/comptes/desinscription/[\w:-]+/>$")
        self.assertEqual(message.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_sent_after_other_emails(self):
        """Une nouvelle tentative (lien de mot de passe...) n'attend pas la fin d'un envoi en nombre."""
        password_reset = EmailLog.objects.create(
            recipient=self.marie.email,
            kind=AccountEmail.PASSWORD_RESET,
            subject="Changement de votre mot de passe",
            user=self.marie,
            attempts=1,
            last_attempt_at=timezone.now() - timedelta(minutes=6),
        )

        with mock.patch("accounts.services.email_retry.EMAILS_PER_PASS", 1):
            retry_due_emails()

        password_reset.refresh_from_db()
        self.log.refresh_from_db()
        self.assertEqual(password_reset.status, EmailStatus.SENT)
        self.assertEqual((self.log.status, self.log.attempts), (EmailStatus.PENDING, 0))

    def test_not_sent_after_unsubscribing(self):
        self.marie.set_promotional_emails_consent(False)
        self.marie.save()

        retry_due_emails()

        self.log.refresh_from_db()
        self.assertEqual((self.log.status, self.log.last_error), (EmailStatus.FAILED, OBSOLETE))
        self.assertEqual(mail.outbox, [])

    def test_not_sent_to_a_former_address(self):
        self.marie.email = "marie.nouvelle@example.com"
        self.marie.save()

        retry_due_emails()

        self.log.refresh_from_db()
        self.assertEqual(self.log.status, EmailStatus.FAILED)
        self.assertEqual(mail.outbox, [])


class MailablePromotionsTests(TestCase):
    """Un pays ou une destination désactivé n'est jamais cité ; une offre épuisée n'est pas envoyée."""

    def setUp(self):
        self.admin = create_admin()
        self.japan = create_country("Japon")

    def test_only_promotions_still_offered_can_be_chosen(self):
        nara = create_destination(self.japan, "Nara", active=False)
        create_promotion(name="Offre valable")
        create_promotion(name="Printemps à Nara", scope=Scope.DESTINATIONS, destinations=[nara])
        exhausted = create_promotion(name="Offre épuisée", max_uses=1)
        create_order(create_client(), create_destination(self.japan), promotion=exhausted)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("manage_send_promotion_mailing"))

        self.assertContains(response, "Offre valable")
        self.assertNotContains(response, "Printemps à Nara")
        self.assertNotContains(response, "Offre épuisée")

    def test_withdrawn_country_not_named_in_the_email(self):
        create_client("marie@example.com", accepts_promotional_emails=True)
        portugal = create_country("Portugal", active=False)
        promotion = create_promotion(scope=Scope.COUNTRIES, countries=[self.japan, portugal])
        send_promotion_mailing(promotion, "Le printemps arrive !", self.admin)

        retry_due_emails()

        self.assertIn("Destinations concernées : Japon.", mail.outbox[0].body)
