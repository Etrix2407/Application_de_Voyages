import html
import re
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import MIN_DAYS_BEFORE_DEPARTURE, Order, Status, StatusChange

from .factories import create_order, departure_in, review_tokens, submit_order


class CreateOrderTests(TestCase):
    def setUp(self):
        self.client_user = create_client()
        self.client.force_login(self.client_user)
        self.country = create_country()
        self.destination = create_destination(self.country, "Kyoto", price_from=Decimal("1000"))
        self.tea = create_activity(self.country, "Cérémonie du thé", price_per_person=Decimal("50"), minimum_age=12)
        self.url = reverse("create_order", args=[self.destination.pk])

    def data(self, **fields):
        departure = departure_in()
        data = {
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=10)).isoformat(),
            "adults": "2",
            "children": "2",
            "activities": [self.tea.pk],
            "remarks": "Chambre calme si possible.",
        }
        data.update(fields)
        return data

    def test_button_shown_to_clients_on_destination_page(self):
        response = self.client.get(reverse("destination_detail", args=[self.destination.pk]))

        self.assertContains(response, self.url)

    def test_button_hidden_from_staff(self):
        self.client.force_login(create_agent())

        response = self.client.get(reverse("destination_detail", args=[self.destination.pk]))

        self.assertNotContains(response, self.url)

    def test_form_offers_only_visible_activities_of_the_country(self):
        create_activity(self.country, "Karaoké fermé", active=False)
        create_activity(create_country("Pérou"), "Trek")

        response = self.client.get(self.url)

        self.assertContains(response, "Cérémonie du thé")
        self.assertContains(response, "à partir de 12 ans")
        self.assertNotContains(response, "Karaoké fermé")
        self.assertNotContains(response, "Trek")

    def test_review_shows_estimate_before_sending(self):
        response = self.client.post(self.url, self.data())

        # (1000 + 50) × 2 adultes + (1000 + 50) × 50 % × 2 enfants
        self.assertContains(response, "3150,00 €")
        self.assertContains(response, "estimation, non contractuel")
        self.assertFalse(Order.objects.exists())

    def test_confirm_creates_pending_order_with_frozen_prices(self):
        response = submit_order(self.client, self.url, self.data(), follow=True)

        self.assertContains(response, "un conseiller vous rappellera sous 48 heures")
        order = Order.objects.get()
        self.assertEqual(order.client, self.client_user)
        self.assertEqual(order.status, Status.PENDING)
        self.assertEqual(order.estimated_price, Decimal("3150.00"))
        self.assertEqual(order.destination_price, Decimal("1000"))
        self.assertEqual(order.activities.get().unit_price, Decimal("50"))
        self.assertEqual(order.remarks, "Chambre calme si possible.")
        change = order.history.get()
        self.assertEqual((change.status, change.author_name), (Status.PENDING, StatusChange.CLIENT_AUTHOR))

    def test_edit_goes_back_to_the_form(self):
        response = self.client.post(self.url, {**self.data(), "edit": ""})

        self.assertTemplateUsed(response, "orders/create.html")
        self.assertContains(response, "Chambre calme si possible.")
        self.assertFalse(Order.objects.exists())

    def test_destination_on_quote(self):
        on_quote = create_destination(self.country, "Sans prix")

        response = self.client.post(reverse("create_order", args=[on_quote.pk]), self.data())

        self.assertContains(response, "sur devis")
        self.assertContains(response, "150,00 €")  # activité seule : 50 × 2 + 50 × 50 % × 2

    def test_invalid_requests_rejected(self):
        too_soon = departure_in(MIN_DAYS_BEFORE_DEPARTURE - 1)
        cases = {
            "départ trop proche": {"departure_date": too_soon.isoformat(), "return_date": (too_soon + timedelta(days=5)).isoformat()},
            "retour avant départ": {"return_date": departure_in(1).isoformat()},
            "aucun adulte": {"adults": "0"},
            "trop de voyageurs": {"adults": "6", "children": "5"},
            "activité d'un autre pays": {"activities": [create_activity(create_country("Pérou")).pk]},
        }
        for reason, fields in cases.items():
            with self.subTest(reason=reason):
                response = self.client.post(self.url, {**self.data(**fields), "confirm": ""})

                self.assertTemplateUsed(response, "orders/create.html")
                self.assertFalse(Order.objects.exists())

    def test_inactive_destination_cannot_be_ordered(self):
        self.destination.active = False
        self.destination.save()

        response = self.client.get(self.url, follow=True)

        self.assertContains(response, "plus proposée")
        self.assertFalse(Order.objects.exists())

    def test_duplicate_pending_order_warns_without_blocking(self):
        data = self.data()
        create_order(
            self.client_user,
            self.destination,
            departure_date=departure_in(),
            return_date=departure_in() + timedelta(days=10),
        )

        review = self.client.post(self.url, data)
        self.assertContains(review, "déjà une demande en attente")
        self.client.post(self.url, {**data, **review_tokens(review), "confirm": ""})

        self.assertEqual(Order.objects.count(), 2)

    def test_no_duplicate_warning_for_other_dates(self):
        create_order(self.client_user, self.destination, departure_date=departure_in(60))

        self.assertNotContains(self.client.post(self.url, self.data()), "déjà une demande en attente")

    def test_estimated_price_cannot_be_forced_by_the_client(self):
        submit_order(self.client, self.url, {**self.data(), "estimated_price": "1"})

        self.assertEqual(Order.objects.get().estimated_price, Decimal("3150.00"))

    def test_review_page_resends_every_field_when_confirming(self):
        second = create_activity(self.country, "Sumo", price_per_person=Decimal("30"))
        review = self.client.post(self.url, self.data(activities=[self.tea.pk, second.pk])).content.decode()

        # On renvoie exactement les champs cachés de la page de vérification, comme le navigateur.
        hidden = re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"', review)
        data = {}
        for name, value in hidden:
            data.setdefault(name, []).append(html.unescape(value))
        self.client.post(self.url, {**data, "confirm": ""})

        order = Order.objects.get()
        self.assertEqual(set(order.activities.values_list("activity__name", flat=True)), {"Cérémonie du thé", "Sumo"})
        self.assertEqual(order.remarks, "Chambre calme si possible.")
        self.assertEqual((order.adults, order.children), (2, 2))


class SubmissionSafetyTests(TestCase):
    """Constats de l'audit : prix modifié avant l'envoi, double clic, destination désactivée."""

    def setUp(self):
        self.client_user = create_client()
        self.client.force_login(self.client_user)
        self.destination = create_destination(create_country(), "Kyoto", price_from=Decimal("1000"))
        self.url = reverse("create_order", args=[self.destination.pk])
        departure = departure_in()
        self.data = {
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=7)).isoformat(),
            "adults": "2",
            "children": "1",
            "remarks": "",
        }
        self.tokens = review_tokens(self.client.post(self.url, self.data))

    def confirm(self, **extra):
        return self.client.post(self.url, {**self.data, **self.tokens, "confirm": "", **extra}, follow=True)

    def test_price_change_after_review_is_shown_before_saving(self):
        self.destination.price_from = Decimal("6000")
        self.destination.save()

        response = self.confirm()

        self.assertContains(response, "Un tarif a changé")
        self.assertContains(response, "15000,00 €")  # (6000 × 2) + (6000 × 50 % × 1)
        self.assertFalse(Order.objects.exists())

        # Le client renvoie la nouvelle page de vérification : la demande est enregistrée au prix affiché.
        submit = self.client.post(self.url, {**self.data, **review_tokens(response), "confirm": ""})
        self.assertEqual(submit.status_code, 302)
        self.assertEqual(Order.objects.get().estimated_price, Decimal("15000.00"))

    def test_double_click_creates_a_single_order(self):
        first = self.confirm()
        second = self.confirm()

        order = Order.objects.get()
        self.assertRedirects(second, reverse("my_order_detail", args=[order.pk]))
        self.assertContains(second, "avait déjà été envoyée")
        self.assertContains(first, "rappellera sous 48 heures")

    def test_confirm_without_review_tokens_shows_review_again(self):
        response = self.client.post(self.url, {**self.data, "confirm": ""})

        self.assertTemplateUsed(response, "orders/review.html")
        self.assertFalse(Order.objects.exists())

    def test_destination_deactivated_between_review_and_confirm(self):
        self.destination.active = False
        self.destination.save()

        response = self.confirm()

        self.assertContains(response, "plus proposée")
        self.assertFalse(Order.objects.exists())
