from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import PASSWORD, create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import Order, Status, StatusChange
from orders.services.status import cancel_by_staff, confirm_by_staff

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
        cancel_by_staff(self.order, self.agent, "Mme Dupont hospitalisée, voyage reporté.")

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
        self.assertEqual(set(order.history.values_list("reason", flat=True)), {""})

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

        self.assertContains(response, "anonymisée")
        self.assertNotContains(response, "arachides")
        self.assertNotContains(response, "hospitalisée")
        self.assertNotContains(response, "client@example.com")

    def test_deletion_page_announces_anonymous_conservation(self):
        self.client.force_login(self.marie)

        self.assertContains(self.client.get(reverse("delete_account")), "de façon anonyme")
