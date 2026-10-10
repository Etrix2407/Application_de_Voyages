from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.email_retry import retry_due_emails
from accounts.tests.email_delivery import SendEmailsImmediately
from accounts.tests.factories import create_client
from catalog.tests.factories import create_country, create_destination

from .factories import create_review, create_trip_done


@override_settings(SITE_URL="https://horizons-lointains.be")
class ReviewInvitationTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        self.marie = create_client()
        self.kyoto = create_destination(create_country())

    def run_command(self):
        call_command("send_trip_reminders", stdout=StringIO())

    def test_invitation_the_day_after_return_once_with_direct_link(self):
        today = timezone.localdate()
        order = create_trip_done(self.marie, self.kyoto, return_date=today - timedelta(days=1))
        create_trip_done(self.marie, self.kyoto, departure_date=today - timedelta(days=5), return_date=today)

        self.run_command()
        self.run_command()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, "Comment s'est passé votre voyage ?")
        self.assertIn(f"https://horizons-lointains.be/avis/voyage/{order.pk}/donner/", message.body)
        log = EmailLog.objects.get()
        self.assertEqual((log.kind, log.user, log.order_number), (EmailKind.REVIEW_INVITATION, self.marie, order.pk))

    def test_no_invitation_once_reviewed(self):
        create_review(create_trip_done(self.marie, self.kyoto))

        self.run_command()

        self.assertEqual(len(mail.outbox), 0)

    def test_retry_not_sent_once_reviewed(self):
        order = create_trip_done(self.marie, self.kyoto)
        with mock.patch(
            "accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur injoignable")
        ):
            self.run_command()
        create_review(order)
        EmailLog.objects.update(last_attempt_at=timezone.now() - timedelta(minutes=6))

        retry_due_emails()

        self.assertEqual(EmailLog.objects.get().status, EmailStatus.FAILED)
        self.assertEqual(len(mail.outbox), 0)
