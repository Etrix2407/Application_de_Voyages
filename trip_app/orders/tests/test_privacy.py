from decimal import Decimal

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import EmailKind, EmailLog, EmailStatus
from accounts.tests.factories import PASSWORD, create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import Order, Status, StatusChange
from orders.services.data_export import orders_data
from orders.services.status import ACCOUNT_DELETED_REASON, cancel_by_staff, confirm_by_staff

from .factories import create_order


class AccountDeletionAnonymizesOrdersTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.agent = create_agent()
        country = create_country()
        self.tea = create_activity(country, "Cérémonie du thé", price_per_person=Decimal("50"))
        self.order = create_order(
            self.marie,
            create_destination(country, "Kyoto", price_from=Decimal("900")),
            [self.tea],
            remarks="Allergie aux arachides, mon mari est diabétique.",
            estimated_price=Decimal("1900.00"),
        )
        StatusChange.objects.create(
            order=self.order,
            status=Status.PENDING,
            author=self.marie,
            author_name=StatusChange.CLIENT_AUTHOR,
            by_client=True,
        )
        confirm_by_staff(self.order, self.agent)
        cancel_by_staff(
            self.order, self.agent, "Mme Dupont hospitalisée.", "Voyage reporté suite à votre hospitalisation."
        )

    def delete_account_through_the_site(self):
        self.client.force_login(self.marie)
        self.client.post(reverse("delete_account"), {"password": PASSWORD})

    def test_order_kept_for_statistics(self):
        self.delete_account_through_the_site()

        order = Order.objects.get(pk=self.order.pk)
        self.assertIsNone(order.client)
        self.assertEqual(order.destination.name, "Kyoto")
        self.assertEqual((order.adults, order.children), (2, 0))
        self.assertEqual(order.estimated_price, Decimal("1900.00"))
        self.assertEqual(order.status, Status.CANCELLED)
        self.assertEqual(order.activities.get().activity, self.tea)

    def test_free_text_erased(self):
        self.delete_account_through_the_site()

        order = Order.objects.get(pk=self.order.pk)
        self.assertEqual(order.remarks, "")
        self.assertEqual(set(order.history.values_list("reason", "internal_reason")), {("", "")})

    def test_history_dates_and_agent_names_kept(self):
        self.delete_account_through_the_site()

        history = Order.objects.get(pk=self.order.pk).history.all()
        self.assertEqual([change.status for change in history], [Status.PENDING, Status.CONFIRMED, Status.CANCELLED])
        self.assertEqual([change.author_name for change in history], ["Client", "Luc Martin", "Luc Martin"])
        self.assertIsNone(history[0].author)

    def test_anonymized_whatever_the_deletion_path(self):
        # Suppression directe en base (ex. purge), sans passer par la page du profil.
        self.marie.delete()

        order = Order.objects.get(pk=self.order.pk)
        self.assertIsNone(order.client)
        self.assertEqual(order.remarks, "")

    def test_other_clients_untouched(self):
        paul = create_client(email="paul@example.com")
        other = create_order(paul, self.order.destination, remarks="Vue sur la mer svp")

        self.delete_account_through_the_site()

        other.refresh_from_db()
        self.assertEqual((other.client, other.remarks), (paul, "Vue sur la mer svp"))

    def test_deleting_an_agent_does_not_anonymize_client_orders(self):
        self.agent.delete()

        order = Order.objects.get(pk=self.order.pk)
        self.assertEqual(order.client, self.marie)
        self.assertNotEqual(order.remarks, "")

    def test_staff_sees_anonymized_order(self):
        self.delete_account_through_the_site()
        self.client.force_login(create_agent(email="autre.agent@example.com"))

        response = self.client.get(reverse("manage_order_detail", args=[self.order.pk]))

        self.assertContains(response, "cette demande n'est plus liée à lui")
        self.assertNotContains(response, "arachides")
        self.assertNotContains(response, "hospitalisée")
        self.assertNotContains(response, "client@example.com")

    def test_deletion_page_announces_anonymous_conservation(self):
        self.client.force_login(self.marie)

        self.assertContains(self.client.get(reverse("delete_account")), "sans votre nom ni vos coordonnées")


class OrdersDataExportTests(TestCase):
    def test_export_includes_internal_reason(self):
        marie = create_client()
        order = create_order(marie, create_destination(create_country()))
        cancel_by_staff(order, create_agent(), "Hôtel partenaire en faillite.", "Destination fermée cette saison.")

        (change,) = orders_data(marie)[0]["history"]

        self.assertEqual(
            (change["reason"], change["internal_reason"]),
            ("Destination fermée cette saison.", "Hôtel partenaire en faillite."),
        )


class PendingOrdersOfDeletedAccountTests(TestCase):
    """Plus personne à rappeler : les demandes en attente sont annulées, le personnel le voit."""

    def setUp(self):
        self.marie = create_client()
        destination = create_destination(create_country(), "Kyoto")
        self.pending = create_order(self.marie, destination, remarks="Merci de m'appeler le soir.")
        self.confirmed = create_order(self.marie, destination)
        confirm_by_staff(self.confirmed, create_agent())

    def test_pending_order_cancelled_with_explanation(self):
        self.marie.delete()

        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Status.CANCELLED)
        self.assertEqual(self.pending.remarks, "")
        change = self.pending.history.get()
        self.assertEqual(change.status, Status.CANCELLED)
        self.assertEqual((change.internal_reason, change.reason), (ACCOUNT_DELETED_REASON, ""))
        self.assertTrue(change.by_client)
        self.assertIsNone(change.author)

    def test_confirmed_order_kept_for_the_agency(self):
        self.marie.delete()

        self.confirmed.refresh_from_db()
        self.assertEqual(self.confirmed.status, Status.CONFIRMED)

    def test_staff_sees_why_and_cannot_confirm(self):
        self.marie.delete()
        self.client.force_login(create_agent(email="autre.agent@example.com"))

        response = self.client.get(reverse("manage_order_detail", args=[self.pending.pk]))

        self.assertContains(response, "Compte client supprimé")
        self.assertNotContains(response, reverse("manage_confirm_order", args=[self.pending.pk]))

    def test_cancelled_when_deleting_through_the_profile_page(self):
        self.client.force_login(self.marie)

        self.client.post(reverse("delete_account"), {"password": PASSWORD})

        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, Status.CANCELLED)
        self.assertEqual(self.pending.history.get().internal_reason, ACCOUNT_DELETED_REASON)


class AccountDeletionEmailTests(TestCase):
    def test_only_the_deletion_email_is_sent_to_the_former_address(self):
        marie = create_client()
        pending = create_order(marie, create_destination(create_country()))
        self.client.force_login(marie)

        # Comme sur le site : l'e-mail part après la validation, donc après la suppression du compte.
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("delete_account"), {"password": PASSWORD})

        pending.refresh_from_db()
        self.assertEqual(pending.status, Status.CANCELLED)
        # Aucun e-mail pour l'annulation de la demande : seulement le dernier message.
        self.assertEqual(
            [(message.to, message.subject) for message in mail.outbox],
            [(["client@example.com"], "Votre compte a été supprimé")],
        )
        # Le journal garde la ligne, sans l'adresse (RGPD), avec le résultat de l'envoi.
        log = EmailLog.objects.get(kind=EmailKind.ACCOUNT_DELETED)
        self.assertEqual((log.recipient, log.status), ("", EmailStatus.SENT))
