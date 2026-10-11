from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.email_retry import OBSOLETE, retry_due_emails
from accounts.tests.factories import create_admin, create_agent, create_client
from promotions.models import PromotionMailing
from promotions.tests.factories import create_promotion


class MailingPageTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin(first_name="Anne", last_name="Durand"))
        self.promotion = create_promotion(code="SOLEIL10")
        self.url = reverse("manage_send_promotion_mailing")
        self.data = {"promotion": self.promotion.pk, "message": "Le printemps arrive !"}

    def test_queued_only_for_promotion_recipients(self):
        marie = create_client("marie@example.com", accepts_promotional_emails=True)
        create_client("sans.accord@example.com")
        create_client("non.confirmee@example.com", accepts_promotional_emails=True, email_confirmed_at=None)
        create_client("inactive@example.com", accepts_promotional_emails=True, is_active=False)

        response = self.client.post(self.url, self.data, follow=True)

        self.assertContains(response, "L&#x27;envoi à 1 client a été programmé")
        mailing = PromotionMailing.objects.get()
        self.assertEqual((mailing.recipients_count, mailing.author_name), (1, "Anne Durand"))
        log = EmailLog.objects.get()
        self.assertEqual(
            (log.user, log.kind, log.status, log.attempts), (marie, EmailKind.PROMOTION, EmailStatus.PENDING, 0)
        )
        self.assertEqual(log.promotion_mailing_number, mailing.pk)
        self.assertEqual(mail.outbox, [])  # rien n'est envoyé pendant la requête
        self.assertContains(response, "envoyée par Anne Durand")  # envoi listé sur la fiche de la promotion

    def test_refused_without_recipients(self):
        response = self.client.post(self.url, self.data, follow=True)

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
        self.client.post(
            reverse("manage_send_promotion_mailing"),
            {"promotion": create_promotion(code="SOLEIL10").pk, "message": "Le printemps arrive !"},
        )
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
