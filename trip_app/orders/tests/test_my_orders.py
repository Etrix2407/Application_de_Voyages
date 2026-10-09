from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import Order, Status, StatusChange
from orders.services.status import TransitionNotAllowed, cancel_by_client

from .factories import create_order, departure_in


class MyOrdersTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.country = create_country()
        self.destination = create_destination(self.country, "Kyoto", price_from=Decimal("1000"))
        self.order = create_order(self.marie, self.destination, estimated_price=Decimal("2100.00"))
        StatusChange.objects.create(order=self.order, status=Status.PENDING, author_name=StatusChange.CLIENT_AUTHOR)

    def test_menu_link_for_clients(self):
        self.assertContains(self.client.get(reverse("home")), reverse("my_orders"))

    def test_list_shows_own_orders_with_key_information(self):
        response = self.client.get(reverse("my_orders"))

        self.assertContains(response, "Kyoto")
        self.assertContains(response, "En attente")
        self.assertContains(response, "2100,00 €")
        self.assertContains(response, reverse("my_order_detail", args=[self.order.pk]))

    def test_list_most_recent_first(self):
        newer = create_order(self.marie, create_destination(self.country, "Osaka"))

        orders = list(self.client.get(reverse("my_orders")).context["orders"])

        self.assertEqual(orders, [newer, self.order])

    def test_other_clients_orders_invisible(self):
        other = create_client(email="autre@example.com")
        foreign = create_order(other, create_destination(self.country, "Nara"))

        self.assertNotContains(self.client.get(reverse("my_orders")), "Nara")
        self.assertEqual(self.client.get(reverse("my_order_detail", args=[foreign.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("cancel_my_order", args=[foreign.pk])).status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.status, Status.PENDING)

    def test_detail_shows_frozen_prices_activities_and_history(self):
        tea = create_activity(self.country, "Cérémonie du thé", price_per_person=Decimal("50"))
        order = create_order(self.marie, self.destination, [tea], remarks="Chambre calme")
        tea.price_per_person = Decimal("999")
        tea.save()

        response = self.client.get(reverse("my_order_detail", args=[order.pk]))

        self.assertContains(response, "Cérémonie du thé (50,00 € par personne)")
        self.assertContains(response, "Chambre calme")
        self.assertContains(response, "estimation, non contractuel")
        self.assertContains(self.client.get(reverse("my_order_detail", args=[self.order.pk])), "Client")

    def test_empty_list(self):
        Order.objects.all().delete()

        self.assertContains(self.client.get(reverse("my_orders")), "pas encore fait de demande")


class ClientCancellationTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.order = create_order(self.marie, create_destination(create_country(), "Kyoto"))
        self.url = reverse("cancel_my_order", args=[self.order.pk])

    def test_cancel_pending_order_with_optional_reason(self):
        self.assertContains(self.client.get(self.url), "Motif (facultatif)")

        response = self.client.post(self.url, {"reason": "Dates impossibles finalement."}, follow=True)

        self.assertContains(response, "Votre demande a été annulée.")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.CANCELLED)
        change = self.order.history.get()
        self.assertEqual(
            (change.status, change.author_name, change.reason),
            (Status.CANCELLED, StatusChange.CLIENT_AUTHOR, "Dates impossibles finalement."),
        )

    def test_cancel_without_reason(self):
        self.client.post(self.url, {"reason": ""})

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.CANCELLED)
        self.assertEqual(self.order.history.get().reason, "")

    def test_confirmed_order_cannot_be_cancelled_by_client(self):
        Order.objects.filter(pk=self.order.pk).update(status=Status.CONFIRMED)

        detail = self.client.get(reverse("my_order_detail", args=[self.order.pk]))
        self.assertContains(detail, "appelez l'agence")
        self.assertNotContains(detail, self.url)
        response = self.client.post(self.url, {"reason": ""}, follow=True)

        self.assertContains(response, "ne peut plus être annulée en ligne")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.CONFIRMED)

    def test_cancelling_twice_is_refused_and_recorded_once(self):
        cancel_by_client(self.order)

        with self.assertRaises(TransitionNotAllowed):
            cancel_by_client(self.order)
        self.assertEqual(self.order.history.count(), 1)

    def test_get_does_not_cancel(self):
        self.client.get(self.url)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.PENDING)


class AfterCreationTests(TestCase):
    def test_new_order_opens_its_detail_page(self):
        marie = create_client()
        self.client.force_login(marie)
        destination = create_destination(create_country(), "Kyoto")
        departure = departure_in()

        response = self.client.post(
            reverse("create_order", args=[destination.pk]),
            {
                "departure_date": departure.isoformat(),
                "return_date": (departure + timedelta(days=5)).isoformat(),
                "adults": "1",
                "children": "0",
                "remarks": "",
                "confirm": "",
            },
            follow=True,
        )

        order = Order.objects.get()
        self.assertRedirects(response, reverse("my_order_detail", args=[order.pk]))
        self.assertContains(response, "un conseiller vous rappellera sous 48 heures")
