from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.emails import MAX_ATTEMPTS, deliver, send_email

from .factories import create_client

TEMPLATE = "accounts/emails/client_password.txt"
LINK = "https://horizons-lointains.be/reinitialisation/abc/jeton-secret/"


class SendEmailTests(TestCase):
    def setUp(self):
        self.marie = create_client(email="marie@example.com", first_name="Marie")

    def send(self):
        # Le TestCase n'achève jamais sa transaction : on exécute les envois prévus à sa validation.
        with self.captureOnCommitCallbacks(execute=True):
            return send_email(
                "marie@example.com",
                EmailKind.CLIENT_PASSWORD_LINK,
                TEMPLATE,
                {"user": self.marie, "link": LINK},
                user=self.marie,
                order_number=42,
            )

    def test_sent_after_commit_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            send_email("marie@example.com", EmailKind.CLIENT_PASSWORD_LINK, TEMPLATE, {"user": self.marie, "link": LINK})
            self.assertEqual(len(mail.outbox), 0)
            self.assertEqual(EmailLog.objects.get().status, EmailStatus.PENDING)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailLog.objects.get().status, EmailStatus.SENT)

    def test_log_without_content_nor_link(self):
        self.send()

        log = EmailLog.objects.get()
        self.assertEqual(
            (log.recipient, log.kind, log.subject, log.status, log.attempts, log.user, log.order_number),
            ("marie@example.com", EmailKind.CLIENT_PASSWORD_LINK, "Changement de votre mot de passe",
             EmailStatus.SENT, 1, self.marie, 42),
        )
        stored = [str(value) for value in EmailLog.objects.values().get().values()]
        self.assertFalse(any("jeton-secret" in value or "Bonjour" in value for value in stored))

    def test_html_and_text_versions(self):
        self.send()

        message = mail.outbox[0]
        self.assertIn(LINK, message.body)
        self.assertEqual(message.reply_to, ["info@horizons-lointains.be"])
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn(f'href="{LINK}"', html)
        self.assertIn("Bonjour Marie,", html)
        self.assertTrue(message.body.endswith("\n\nL'équipe Horizons Lointains\n"))
        self.assertIn("L&#x27;équipe Horizons Lointains", html)

    @override_settings(EMAIL_TEST_MODE=True, EMAIL_TEST_RECIPIENT="essais@agence.be")
    def test_test_mode_redirects_to_test_address(self):
        self.send()

        message = mail.outbox[0]
        self.assertEqual(message.to, ["essais@agence.be"])
        self.assertIn("marie@example.com", message.subject)
        self.assertEqual(EmailLog.objects.get().recipient, "marie@example.com")

    @mock.patch("accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur injoignable"))
    def test_failure_does_not_block_and_is_logged(self, _send):
        with self.assertLogs("accounts.services.emails", level="ERROR"):
            self.send()  # aucune exception : l'action de l'utilisateur continue

        log = EmailLog.objects.get()
        self.assertEqual((log.status, log.attempts, log.last_error), (EmailStatus.PENDING, 1, "serveur injoignable"))

        # Après la dernière tentative, l'envoi passe à l'état « échec ».
        with self.assertLogs("accounts.services.emails", level="ERROR"):
            for _ in range(MAX_ATTEMPTS - 1):
                deliver(log, mail.EmailMultiAlternatives())
        self.assertEqual(log.status, EmailStatus.FAILED)

    def test_account_deletion_erases_address_and_link(self):
        self.send()

        self.marie.delete()

        log = EmailLog.objects.get()
        self.assertEqual((log.recipient, log.user), ("", None))
