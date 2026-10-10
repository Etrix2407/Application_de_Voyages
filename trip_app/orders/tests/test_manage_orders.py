from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Order, Status
from orders.services.filtering import filter_orders
from orders.views.manage import ORDERS_PER_PAGE

from .factories import create_order, departure_in


class StaffOrderListTests(TestCase):
    url = reverse("manage_orders")

    def setUp(self):
        self.client.force_login(create_agent())
        self.japan = create_country("Japon")
        self.peru = create_country("Pérou")
        self.kyoto = create_destination(self.japan, "Kyoto")
        self.cusco = create_destination(self.peru, "Cusco")
        self.marie = create_client(email="marie@example.com", last_name="Lefèvre", first_name="Hélène")
        self.paul = create_client(email="paul@example.com", last_name="Durand", first_name="Paul")
        self.old = create_order(self.marie, self.kyoto, departure_date=departure_in(30))
        self.new = create_order(self.paul, self.cusco, departure_date=departure_in(90))
        Order.objects.filter(pk=self.new.pk).update(status=Status.CONFIRMED)

    def listed(self, **params):
        return list(self.client.get(self.url, params).context["page"].object_list)

    def test_menu_link_for_staff(self):
        self.assertContains(self.client.get(reverse("home")), self.url)

    def test_all_orders_most_recent_first(self):
        self.assertEqual(self.listed(), [self.new, self.old])

    def test_sort_oldest_first(self):
        self.assertEqual(self.listed(sort="ancien"), [self.old, self.new])

    def test_filter_by_status(self):
        self.assertEqual(self.listed(status=Status.CONFIRMED), [self.new])

    def test_filter_by_country_and_destination(self):
        self.assertEqual(self.listed(country=self.japan.pk), [self.old])
        self.assertEqual(self.listed(destination=self.cusco.pk), [self.new])

    def test_filter_by_client_without_accents(self):
        self.assertEqual(self.listed(client="helene lefevre"), [self.old])
        self.assertEqual(self.listed(client="PAUL@"), [self.new])

    def test_filter_by_client_in_one_query(self):
        # Les clients ne sont pas chargés en Python : la base filtre via une sous-requête.
        with self.assertNumQueries(1):
            self.assertEqual(list(filter_orders({"client": "Hélène"})), [self.old])

    def test_filter_by_departure_period(self):
        self.assertEqual(
            self.listed(departure_from=departure_in(60).isoformat(), departure_to=departure_in(120).isoformat()),
            [self.new],
        )

    def test_invalid_period_reported(self):
        response = self.client.get(
            self.url, {"departure_from": departure_in(60).isoformat(), "departure_to": departure_in(10).isoformat()}
        )

        self.assertContains(response, "La fin de la période doit être après son début.")

    def test_combined_filters(self):
        self.assertEqual(self.listed(country=self.japan.pk, status=Status.CONFIRMED), [])

    def test_anonymized_order_listed(self):
        self.marie.delete()

        self.assertContains(self.client.get(self.url), "Client supprimé")

    def test_pagination_keeps_filters(self):
        for _ in range(ORDERS_PER_PAGE):
            create_order(self.marie, self.kyoto)

        page_1 = self.client.get(self.url, {"country": self.japan.pk})
        page_2 = self.client.get(self.url, {"country": self.japan.pk, "page": 2})

        self.assertContains(page_1, f"country={self.japan.pk}&amp;page=2")
        self.assertEqual(len(page_2.context["page"].object_list), 1)


class StaffOrderDetailTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.marie = create_client(phone="+33612345678")
        self.order = create_order(
            self.marie,
            create_destination(create_country(), "Kyoto", price_from=Decimal("900")),
            return_date=departure_in() + timedelta(days=7),
            remarks="Allergie aux arachides.",
        )
        self.url = reverse("manage_order_detail", args=[self.order.pk])

    def test_full_detail_with_client_contact(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'href="tel:+33612345678"')
        self.assertContains(response, 'href="mailto:client@example.com"')
        self.assertContains(response, "Allergie aux arachides.")
        self.assertContains(response, "Historique")
