from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.services.email_retry import OBSOLETE, retry_due_emails
from accounts.tests.email_delivery import SendEmailsImmediately
from accounts.tests.factories import PASSWORD, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from common.text import euros
from orders.models import Order, OrderStatus
from orders.services.status import cancel_by_client, cancel_by_staff, confirm_by_staff
from promotions.tests.factories import create_promotion

from .factories import create_order, departure_in, submit_order


class OrderEmailsTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        self.marie = create_client(phone="0470 12 34 56")
        self.agent = create_agent()
        self.destination = create_destination(create_country("Japon"), "Kyoto", price_from=Decimal("1000"))

    def test_placed_order_sends_receipt_to_client_and_alert_to_reservations(self):
        promotion = create_promotion(name="Semaine du Japon")
        self.client.force_login(self.marie)
        departure = departure_in()
        data = {
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=10)).isoformat(),
            "adults": "2",
            "children": "0",
            "remarks": "",
        }

        submit_order(self.client, reverse("create_order", args=[self.destination.pk]), data)

        order = Order.objects.get()
        self.assertEqual(order.promotion, promotion)
        receipt, alert = mail.outbox
        self.assertEqual(receipt.to, [self.marie.email])
        for text in ("48 h", f"N° de demande : {order.pk}", "Kyoto (Japon)", "Semaine du Japon",
                     euros(order.discount), euros(order.estimated_price), "estimation, non contractuelle"):
            self.assertIn(text, receipt.body)
        self.assertEqual(alert.to, ["reservations@horizons-lointains.be"])
        for text in (str(order.pk), "Kyoto (Japon)", "Marie Dupont", reverse("manage_order_detail", args=[order.pk])):
            self.assertIn(text, alert.body)
        self.assertNotIn(self.marie.email, alert.body)
        self.assertNotIn(self.marie.phone, alert.body)
        logged = EmailLog.objects.filter(order_number=order.pk)
        self.assertEqual(
            set(logged.values_list("kind", "user")),
            {(EmailKind.ORDER_PLACED, self.marie.pk), (EmailKind.NEW_ORDER_ALERT, None)},
        )

    def test_confirmation_gives_confirmed_price_and_advisor_name(self):
        order = create_order(self.marie, self.destination, estimated_price=Decimal("1500.00"))

        confirm_by_staff(order, self.agent)

        (email,) = mail.outbox
        self.assertEqual(email.to, [self.marie.email])
        self.assertIn("Luc Martin", email.body)
        self.assertIn(f"Prix confirmé : {euros(Decimal('2000.00'))}", email.body)

    def test_client_cancellation_is_acknowledged(self):
        order = create_order(self.marie, self.destination)

        cancel_by_client(order, "Changement de programme.")

        (email,) = mail.outbox
        self.assertEqual(email.to, [self.marie.email])
        self.assertIn("bien enregistré l'annulation", email.body)

    def test_agency_cancellation_gives_explanation_but_never_internal_reason(self):
        order = create_order(self.marie, self.destination)

        cancel_by_staff(order, self.agent, "Client agressif au téléphone.", "Plus de places disponibles.")

        (email,) = mail.outbox
        self.assertIn("Plus de places disponibles.", email.body)
        self.assertIn("excuser", email.body)
        self.assertNotIn("agressif", email.body)

    def test_agency_cancellation_without_explanation_is_neutral(self):
        order = create_order(self.marie, self.destination)

        cancel_by_staff(order, self.agent, "Client injoignable.")

        (email,) = mail.outbox
        self.assertNotIn("Explication", email.body)
        self.assertNotIn("injoignable", email.body)

    def test_account_deletion_sends_no_order_email(self):
        order = create_order(self.marie, self.destination)
        self.client.force_login(self.marie)

        self.client.post(reverse("delete_account"), {"password": PASSWORD})

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertFalse(EmailLog.objects.filter(kind__startswith="order_").exists())

def failed_once(user, kind, order):
    """E-mail en attente, première tentative ratée il y a 6 minutes : repris au prochain passage."""
    return EmailLog.objects.create(
        recipient=user.email if user else "reservations@horizons-lointains.be",
        kind=kind,
        subject="Objet",
        user=user,
        order_number=order.pk,
        attempts=1,
        last_attempt_at=timezone.now() - timedelta(minutes=6),
    )


class OrderEmailsRebuildTests(SendEmailsImmediately, TestCase):
    def setUp(self):
        self.marie = create_client()
        self.agent = create_agent()
        self.order = create_order(self.marie, create_destination(create_country("Japon"), "Kyoto"))

    def test_rebuilt_on_retry(self):
        # Type → (action qui amène la demande dans l'état annoncé, textes attendus, texte jamais repris).
        cases = {
            EmailKind.ORDER_PLACED: (lambda order: None, ["Kyoto (Japon)", "Prix estimé"], None),
            EmailKind.ORDER_CONFIRMED: (lambda order: confirm_by_staff(order, self.agent), ["Luc Martin"], None),
            EmailKind.ORDER_CANCELLED_BY_CLIENT: (
                lambda order: cancel_by_client(order, "Changement de programme."),
                ["bien enregistré l'annulation"],
                None,
            ),
            EmailKind.ORDER_CANCELLED_BY_AGENCY: (
                lambda order: cancel_by_staff(order, self.agent, "Client agressif.", "Plus de places disponibles."),
                ["Plus de places disponibles."],
                "agressif",
            ),
            EmailKind.NEW_ORDER_ALERT: (lambda order: None, ["Marie Dupont", "Kyoto (Japon)"], None),
        }
        for kind, (action, expected, never) in cases.items():
            with self.subTest(kind=kind):
                order = create_order(self.marie, self.order.destination)
                action(order)
                EmailLog.objects.all().delete()
                mail.outbox.clear()
                failed_once(None if kind == EmailKind.NEW_ORDER_ALERT else self.marie, kind, order)

                self.assertEqual(retry_due_emails(), 1)

                (email,) = mail.outbox
                html = email.alternatives[0][0]
                for text in expected:
                    self.assertIn(text, email.body)
                if never:
                    self.assertNotIn(never, email.body)
                    self.assertNotIn(never, html)

    def test_never_rebuilt_for_a_former_address(self):
        log = failed_once(self.marie, EmailKind.ORDER_PLACED, self.order)
        self.marie.email = "marie.nouvelle@example.com"
        self.marie.save()

        retry_due_emails()

        log.refresh_from_db()
        self.assertEqual((log.status, log.last_error), (EmailStatus.FAILED, OBSOLETE))
        self.assertEqual(mail.outbox, [])