from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.account_deletion import delete_account
from accounts.services.email_retry import NOT_REBUILDABLE, OBSOLETE, retry_due_emails
from accounts.services.privacy import purge_old_email_log

from .factories import create_admin, create_agent, create_client

SMTP_DOWN = mock.patch(
    "accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur injoignable")
)


def pending_log(user, attempts, minutes_ago, **fields):
    """E-mail déjà tenté `attempts` fois, la dernière fois il y a `minutes_ago` minutes."""
    fields.setdefault("kind", EmailKind.CLIENT_PASSWORD_LINK)
    return EmailLog.objects.create(
        recipient=user.email,
        subject="Changement de votre mot de passe",
        user=user,
        attempts=attempts,
        last_attempt_at=timezone.now() - timedelta(minutes=minutes_ago),
        **fields,
    )


class RetryTests(TestCase):
    def setUp(self):
        self.marie = create_client(email="marie@example.com")

    def test_second_attempt_after_5_minutes(self):
        too_soon = pending_log(self.marie, attempts=1, minutes_ago=4)
        due = pending_log(self.marie, attempts=1, minutes_ago=6)

        self.assertEqual(retry_due_emails(), 1)

        due.refresh_from_db()
        too_soon.refresh_from_db()
        self.assertEqual((due.status, due.attempts), (EmailStatus.SENT, 2))
        self.assertEqual((too_soon.status, too_soon.attempts), (EmailStatus.PENDING, 1))
        # Message reconstruit avec un lien de mot de passe neuf.
        self.assertRegex(mail.outbox[0].body, r"/reinitialisation/[\w-]+/[\w-]+/")

    def test_third_attempt_after_15_minutes(self):
        too_soon = pending_log(self.marie, attempts=2, minutes_ago=14)
        due = pending_log(self.marie, attempts=2, minutes_ago=16)

        self.assertEqual(retry_due_emails(), 1)

        due.refresh_from_db()
        too_soon.refresh_from_db()
        self.assertEqual(due.status, EmailStatus.SENT)
        self.assertEqual(too_soon.status, EmailStatus.PENDING)

    def test_failed_after_third_attempt_with_reason(self):
        log = pending_log(self.marie, attempts=2, minutes_ago=16)

        with SMTP_DOWN, self.assertLogs("accounts.services.emails", level="ERROR"):
            retry_due_emails()

        log.refresh_from_db()
        self.assertEqual((log.status, log.attempts, log.last_error), (EmailStatus.FAILED, 3, "serveur injoignable"))

    def test_no_security_link_to_a_former_address(self):
        log = pending_log(self.marie, attempts=1, minutes_ago=6)
        self.marie.email = "marie.nouvelle@example.com"
        self.marie.save()

        retry_due_emails()

        log.refresh_from_db()
        self.assertEqual((log.status, log.last_error), (EmailStatus.FAILED, OBSOLETE))
        self.assertEqual(mail.outbox, [])

    def test_email_change_confirmation_never_rebuilt(self):
        log = pending_log(self.marie, attempts=1, minutes_ago=6, kind=EmailKind.EMAIL_CHANGE_CONFIRMATION)

        retry_due_emails()

        log.refresh_from_db()
        self.assertEqual((log.status, log.last_error), (EmailStatus.FAILED, NOT_REBUILDABLE))
        self.assertEqual(mail.outbox, [])


class ManualResendTests(TestCase):
    def setUp(self):
        self.marie = create_client(email="marie@example.com")
        self.log = pending_log(self.marie, attempts=3, minutes_ago=60, status=EmailStatus.FAILED, last_error="refusé")
        self.client.force_login(create_agent())

    def test_failures_listed_and_resent(self):
        self.assertContains(self.client.get(reverse("email_failure_list")), "marie@example.com")

        response = self.client.post(reverse("resend_email", args=[self.log.pk]), follow=True)

        self.assertContains(response, "a été renvoyé à marie@example.com")
        self.log.refresh_from_db()
        self.assertEqual((self.log.status, self.log.attempts), (EmailStatus.SENT, 1))
        self.assertEqual(mail.outbox[0].to, ["marie@example.com"])
        self.assertEqual(EmailLog.objects.count(), 1)  # même ligne du journal, remise en attente

    def test_failed_resend_goes_back_to_automatic_attempts(self):
        with SMTP_DOWN, self.assertLogs("accounts.services.emails", level="ERROR"):
            self.client.post(reverse("resend_email", args=[self.log.pk]))

        self.log.refresh_from_db()
        self.assertEqual((self.log.status, self.log.attempts), (EmailStatus.PENDING, 1))

    def test_emails_that_cannot_be_resent_are_not_listed(self):
        self.log.last_error = OBSOLETE
        self.log.save()

        self.assertNotContains(self.client.get(reverse("email_failure_list")), "marie@example.com")


class AgentActivationResendTests(TestCase):
    def setUp(self):
        self.new_agent = create_agent(email="nouvel.agent@example.com")
        self.new_agent.set_unusable_password()  # invité : pas encore de mot de passe
        self.new_agent.save()
        self.log = pending_log(
            self.new_agent, attempts=3, minutes_ago=60, status=EmailStatus.FAILED, kind=EmailKind.AGENT_ACTIVATION
        )
        self.url = reverse("resend_email", args=[self.log.pk])

    def test_agents_cannot_resend(self):
        self.client.force_login(create_agent())

        self.assertNotContains(self.client.get(reverse("email_failure_list")), self.url)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertEqual(mail.outbox, [])

    def test_administrator_can_resend(self):
        self.client.force_login(create_admin())

        self.client.post(self.url)

        self.assertEqual(mail.outbox[0].to, ["nouvel.agent@example.com"])
        # Lien neuf de l'invitation (7 jours), pas celui de « mot de passe oublié ».
        self.assertRegex(mail.outbox[0].body, r"/activation/[\w-]+/[\w-]+/")


class AccountEmailsRetryTests(TestCase):
    def test_staff_password_link_resent_by_administrator_only(self):
        agent = create_agent(email="luc@example.com")
        log = pending_log(agent, attempts=3, minutes_ago=60, status=EmailStatus.FAILED, kind=EmailKind.STAFF_PASSWORD_LINK)
        url = reverse("resend_email", args=[log.pk])

        self.client.force_login(create_agent())
        self.assertEqual(self.client.post(url).status_code, 403)

        self.client.force_login(create_admin())
        self.client.post(url)
        self.assertEqual(mail.outbox[0].to, ["luc@example.com"])
        self.assertRegex(mail.outbox[0].body, r"/activation/[\w-]+/[\w-]+/")

    def test_password_changed_notice_retried(self):
        log = pending_log(create_client(), attempts=1, minutes_ago=6, kind=EmailKind.PASSWORD_CHANGED)

        retry_due_emails()

        log.refresh_from_db()
        self.assertEqual(log.status, EmailStatus.SENT)
        self.assertIn("vient d'être modifié", mail.outbox[0].body)

    def test_deletion_emails_never_resent_nor_listed(self):
        kinds = [EmailKind.ACCOUNT_DELETED, EmailKind.UNCONFIRMED_ACCOUNT_DELETED, EmailKind.STAFF_ACCOUNT_DELETED]
        for number, kind in enumerate(kinds):
            user = create_client(email=f"parti{number}@example.com")
            with SMTP_DOWN, self.assertLogs("accounts.services.emails", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    delete_account(user, kind)

        retry_due_emails(now=timezone.now() + timedelta(minutes=6))

        self.assertEqual(
            set(EmailLog.objects.values_list("recipient", "status", "last_error")),
            {("", EmailStatus.FAILED, NOT_REBUILDABLE)},
        )
        self.client.force_login(create_admin())
        self.assertNotContains(self.client.get(reverse("email_failure_list")), "Votre compte a été supprimé")


class AddressToCheckTests(TestCase):
    def setUp(self):
        self.marie = create_client(email="marie@example.com")
        self.client.force_login(create_agent())

    def fail(self, count):
        for _ in range(count):
            pending_log(self.marie, attempts=3, minutes_ago=30, status=EmailStatus.FAILED)

    def is_marked(self):
        return "Adresse à vérifier" in self.client.get(reverse("client_list")).content.decode()

    def test_marked_after_3_different_failures(self):
        self.fail(2)
        self.assertFalse(self.is_marked())

        self.fail(1)
        self.assertTrue(self.is_marked())

    def test_unmarked_after_a_successful_email(self):
        self.fail(3)

        pending_log(self.marie, attempts=1, minutes_ago=1, status=EmailStatus.SENT)

        self.assertFalse(self.is_marked())

    def test_unmarked_when_address_changes(self):
        self.fail(3)

        self.marie.email = "marie.nouvelle@example.com"
        self.marie.save()

        self.assertFalse(self.is_marked())


class EmailLogRetentionTests(TestCase):
    def test_log_kept_one_year(self):
        now = timezone.now()
        kept = EmailLog.objects.create(kind=EmailKind.PASSWORD_RESET, subject="Objet", created_at=now - timedelta(days=364))
        EmailLog.objects.create(kind=EmailKind.PASSWORD_RESET, subject="Objet", created_at=now - timedelta(days=366))

        self.assertEqual(purge_old_email_log(now), 1)
        self.assertEqual(list(EmailLog.objects.all()), [kept])
