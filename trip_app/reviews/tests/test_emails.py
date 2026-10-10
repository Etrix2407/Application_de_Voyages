"""E-mails envoyés au client sur son avis (v5)."""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.template.defaultfilters import date
from django.test import TestCase
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.email_retry import retry_due_emails
from accounts.tests.email_delivery import SendEmailsImmediately
from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.services.status import cancel_by_staff
from reviews.models import RefusalReason, ReviewStatus
from reviews.services.moderation import hide, publish, refuse
from reviews.services.responses import save_response

from .factories import create_review, create_trip_done


class ReviewEmailTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        self.agent = create_agent(first_name="Luc")
        self.julie = create_client(first_name="Julie", email="julie@example.com")
        self.trip = create_trip_done(self.julie, create_destination(create_country(), "Kyoto"))
        self.review = create_review(self.trip, title="Séjour inoubliable")

    def assertSentToJulie(self, kind):
        """Un seul e-mail, à Julie, noté au journal avec son compte et sa demande ; renvoie son texte."""
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["julie@example.com"])
        log = EmailLog.objects.get()
        self.assertEqual((log.kind, log.user, log.order_number), (kind, self.julie, self.trip.pk))
        return mail.outbox[0].body

    def test_published(self):
        publish(self.review)

        body = self.assertSentToJulie(EmailKind.REVIEW_PUBLISHED)
        self.assertEqual(mail.outbox[0].subject, "Merci, votre avis est en ligne")
        self.assertIn(f"/catalogue/destinations/{self.trip.destination_id}/", body)

    def test_refused_with_reason_and_correction_deadline(self):
        refuse(self.review, RefusalReason.OTHER, "Merci de retirer le nom du guide.")

        body = self.assertSentToJulie(EmailKind.REVIEW_REFUSED)
        self.assertIn("Motif : Autre — Merci de retirer le nom du guide.", body)
        deadline = date(timezone.localtime(self.review.created_at + timedelta(days=30)), "j F Y")
        self.assertIn(f"Vous pouvez corriger votre avis jusqu'au {deadline}", body)

    def test_deadline_passed_instead_of_correction_reminder(self):
        self.review.created_at = timezone.now() - timedelta(days=31)
        self.review.save()

        refuse(self.review, RefusalReason.OFF_TOPIC)

        body = self.assertSentToJulie(EmailKind.REVIEW_REFUSED)
        self.assertIn("Motif : Hors sujet", body)
        self.assertIn("Le délai de 30 jours pour corriger cet avis est dépassé.", body)
        self.assertNotIn("Vous pouvez corriger", body)

    def test_hidden_after_publication_same_email_as_refusal(self):
        self.review.status = ReviewStatus.PUBLISHED
        self.review.save()

        hide(self.review, RefusalReason.ABUSIVE)

        body = self.assertSentToJulie(EmailKind.REVIEW_REFUSED)
        self.assertIn("Motif : Langage injurieux", body)
        self.assertIn("Vous pouvez corriger votre avis", body)

    def test_trip_cancelled_without_correction_reminder(self):
        cancel_by_staff(self.trip, self.agent, "Voyage non effectué.")

        body = self.assertSentToJulie(EmailKind.REVIEW_REFUSED)
        self.assertIn("Motif : Voyage annulé", body)
        self.assertNotIn("corriger", body)

    def test_agency_response_created_then_updated(self):
        self.review.status = ReviewStatus.PUBLISHED
        self.review.save()

        save_response(self.review, self.agent, "Merci Julie !")
        save_response(self.review, self.agent, "Merci beaucoup Julie !")

        self.assertEqual([message.subject for message in mail.outbox], ["Réponse de l'agence à votre avis"] * 2)
        self.assertIn("L'agence a répondu à votre avis", mail.outbox[0].body)
        self.assertIn("L'agence a modifié sa réponse", mail.outbox[1].body)
        self.assertIn("Merci beaucoup Julie !", mail.outbox[1].body)
        self.assertEqual(EmailLog.objects.filter(kind=EmailKind.REVIEW_RESPONSE, user=self.julie).count(), 2)

    def test_failed_email_rebuilt_by_retry(self):
        with mock.patch(
            "accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur injoignable")
        ):
            refuse(self.review, RefusalReason.OFF_TOPIC)
        EmailLog.objects.update(last_attempt_at=timezone.now() - timedelta(minutes=6))

        self.assertEqual(retry_due_emails(), 1)

        self.assertEqual(EmailLog.objects.get().status, EmailStatus.SENT)
        self.assertIn("Motif : Hors sujet", self.assertSentToJulie(EmailKind.REVIEW_REFUSED))

    def test_nothing_for_deleted_client(self):
        self.julie.delete()
        self.review.refresh_from_db()

        publish(self.review)

        self.assertEqual(mail.outbox, [])
        self.assertFalse(EmailLog.objects.exists())
