from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.email_retry import retry_due_emails
from accounts.tests.email_delivery import SendEmailsImmediately
from accounts.tests.factories import create_agent, create_client
from catalog.models import Visa
from catalog.tests.factories import create_country, create_destination
from orders.models import Order, Status
from orders.services.reminders import send_departure_reminders
from orders.services.status import confirm_by_staff

from .factories import create_order, departure_in

OFFSET_LINE = "Décalage horaire le jour du départ : "


class DepartureReminderTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        self.marie = create_client()
        self.country = create_country(visa=Visa.E_VISA, currency="yen")
        self.kyoto = create_destination(self.country)

    def run_command(self):
        # Ce que fait chaque jour la commande send_trip_reminders pour les départs.
        send_departure_reminders()

    def confirmed_order(self, days: int, **fields):
        fields.setdefault("status", Status.CONFIRMED)
        return create_order(self.marie, self.kyoto, departure_date=departure_in(days), **fields)

    def test_reminder_seven_days_before_departure(self):
        order = self.confirmed_order(7)
        self.confirmed_order(8)

        self.run_command()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual((message.to, message.subject), (["client@example.com"], "Votre départ approche"))
        self.assertIn("Une carte d'identité valide suffit pour ce pays.", message.body)
        self.assertIn("Visa pour les Belges : Visa électronique (e-visa)", message.body)
        self.assertIn(f"{OFFSET_LINE}+", message.body)
        self.assertIn("Monnaie : yen", message.body)
        log = EmailLog.objects.get()
        self.assertEqual((log.kind, log.user, log.order_number), (EmailKind.DEPARTURE_REMINDER, self.marie, order.pk))

    def test_passport_required_text(self):
        self.country.passport_required = True
        self.country.save()
        self.confirmed_order(7)

        self.run_command()

        self.assertIn("Un passeport valide est obligatoire pour ce pays.", mail.outbox[0].body)

    def test_time_offset_line_omitted_without_time_zone(self):
        self.country.time_zone = ""
        self.country.save()
        self.confirmed_order(7)

        self.run_command()

        self.assertNotIn(OFFSET_LINE, mail.outbox[0].body)
        self.assertIn("Monnaie : yen", mail.outbox[0].body)

    def test_catch_up_until_departure_then_never_twice(self):
        self.confirmed_order(3)
        self.confirmed_order(-1)  # Départ passé : trop tard.

        self.run_command()
        self.run_command()

        self.assertEqual(len(mail.outbox), 1)

    def test_only_confirmed_orders_of_existing_clients(self):
        self.confirmed_order(5, status=Status.PENDING)
        self.confirmed_order(5, status=Status.CANCELLED)
        create_order(None, self.kyoto, departure_date=departure_in(5), status=Status.CONFIRMED)

        self.run_command()

        self.assertEqual(len(mail.outbox), 0)

    def test_late_confirmation_sends_reminder_at_once(self):
        soon = self.confirmed_order(5, status=Status.PENDING)
        later = self.confirmed_order(30, status=Status.PENDING)
        agent = create_agent()

        confirm_by_staff(soon, agent)
        confirm_by_staff(later, agent)

        # « Demande confirmée » d'abord, puis le rappel ; rien d'autre pour le départ lointain.
        sent = list(EmailLog.objects.order_by("pk").values_list("order_number", "kind"))
        self.assertEqual(sent, [
            (soon.pk, EmailKind.ORDER_CONFIRMED),
            (soon.pk, EmailKind.DEPARTURE_REMINDER),
            (later.pk, EmailKind.ORDER_CONFIRMED),
        ])
        self.run_command()
        self.assertEqual(EmailLog.objects.filter(kind=EmailKind.DEPARTURE_REMINDER).count(), 1)

    def test_retry_rebuilds_reminder_unless_cancelled(self):
        kept = self.confirmed_order(5)
        cancelled = self.confirmed_order(5)
        with mock.patch(
            "accounts.services.emails.EmailMultiAlternatives.send", side_effect=OSError("serveur injoignable")
        ):
            self.run_command()
        Order.objects.filter(pk=cancelled.pk).update(status=Status.CANCELLED)
        EmailLog.objects.update(last_attempt_at=timezone.now() - timedelta(minutes=6))

        retry_due_emails()

        statuses = dict(EmailLog.objects.values_list("order_number", "status"))
        self.assertEqual(statuses, {kept.pk: EmailStatus.SENT, cancelled.pk: EmailStatus.FAILED})
        self.assertIn("Monnaie : yen", mail.outbox[0].body)
