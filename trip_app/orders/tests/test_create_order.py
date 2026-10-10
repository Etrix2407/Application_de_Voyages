import html
import re
from datetime import timedelta
from unittest import mock
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from accounts.services.sign_up import confirm
from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import (
    MAX_DAYS_BEFORE_DEPARTURE,
    MAX_REMARKS_LENGTH,
    MAX_STAY_DAYS,
    MAX_TRAVELLERS,
    MIN_DAYS_BEFORE_DEPARTURE,
    Order,
    Status,
    StatusChange,
)
from orders.services import placing
from orders.services.placing import MAX_ORDERS_PER_DAY, DailyLimitReached, place_order

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
            "départ trop proche": {
                "departure_date": too_soon.isoformat(),
                "return_date": (too_soon + timedelta(days=5)).isoformat(),
            },
            "retour avant départ": {"return_date": departure_in(1).isoformat()},
            "aucun adulte": {"adults": "0"},
            "trop de voyageurs": {"adults": "6", "children": "5"},
            "départ dans plus de deux ans": {
                "departure_date": departure_in(MAX_DAYS_BEFORE_DEPARTURE + 1).isoformat(),
                "return_date": departure_in(MAX_DAYS_BEFORE_DEPARTURE + 5).isoformat(),
            },
            "séjour trop long": {"return_date": (departure_in() + timedelta(days=MAX_STAY_DAYS + 1)).isoformat()},
            "remarques trop longues": {"remarks": "a" * (MAX_REMARKS_LENGTH + 1)},
            "activité d'un autre pays": {"activities": [create_activity(create_country("Pérou")).pk]},
        }
        for reason, fields in cases.items():
            with self.subTest(reason=reason):
                response = self.client.post(self.url, {**self.data(**fields), "confirm": ""})

                self.assertTemplateUsed(response, "orders/create.html")
                self.assertFalse(Order.objects.exists())

    def test_rule_refused_at_the_last_moment_shows_message(self):
        # Ex. activité désactivée entre la page de vérification et l'envoi.
        refusal = ValidationError({"activity": "Cette activité n'est plus proposée."})
        with mock.patch("orders.views.client.place_order", side_effect=refusal):
            response = submit_order(self.client, self.url, self.data())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/create.html")
        self.assertContains(response, "Cette activité n&#x27;est plus proposée.")
        self.assertFalse(Order.objects.exists())

    def test_form_shows_limits_to_the_browser(self):
        response = self.client.get(self.url)
        self.assertContains(response, f'max="{MAX_TRAVELLERS}"')

        self.assertContains(response, f'max="{departure_in(MAX_DAYS_BEFORE_DEPARTURE).isoformat()}"')
        self.assertContains(response, f'maxlength="{MAX_REMARKS_LENGTH}"')
        self.assertContains(response, "dans les deux ans")

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

        self.assertContains(response, "a changé depuis votre vérification")
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


class DailyLimitTests(TestCase):
    def setUp(self):
        self.client_user = create_client()
        self.client.force_login(self.client_user)
        self.destination = create_destination(create_country(), "Kyoto")
        self.url = reverse("create_order", args=[self.destination.pk])

    def send_orders(self, count, client=None):
        for _ in range(count):
            create_order(client or self.client_user, self.destination)

    def test_form_refused_once_limit_reached(self):
        self.send_orders(MAX_ORDERS_PER_DAY)

        response = self.client.get(self.url, follow=True)

        self.assertRedirects(response, reverse("my_orders"))
        self.assertContains(response, "appelez l&#x27;agence")

    def test_last_allowed_order_still_accepted(self):
        self.send_orders(MAX_ORDERS_PER_DAY - 1)

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_cancelled_orders_count_too(self):
        self.send_orders(MAX_ORDERS_PER_DAY)
        Order.objects.update(status=Status.CANCELLED)

        self.assertRedirects(self.client.get(self.url), reverse("my_orders"))

    def test_orders_older_than_a_day_not_counted(self):
        self.send_orders(MAX_ORDERS_PER_DAY)
        Order.objects.update(created_at=timezone.now() - timedelta(days=1, minutes=1))

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_other_clients_not_affected(self):
        self.send_orders(MAX_ORDERS_PER_DAY, client=create_client(email="paul@example.com"))

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_service_refuses_too(self):
        self.send_orders(MAX_ORDERS_PER_DAY)
        data = {
            "departure_date": departure_in(),
            "return_date": departure_in() + timedelta(days=7),
            "adults": 1,
            "children": 0,
            "remarks": "",
            "activities": [],
        }

        with self.assertRaises(DailyLimitReached):
            place_order(self.client_user, self.destination, data)
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_DAY)

    def test_last_allowed_order_taken_meanwhile_refused(self):
        # Deux envois simultanés à 9 demandes sur 10 : l'autre envoi enregistre la sienne juste avant.
        self.send_orders(MAX_ORDERS_PER_DAY - 1)
        real_create_order = placing._create_order

        def create(*args, **kwargs):
            self.send_orders(1)
            return real_create_order(*args, **kwargs)

        departure = departure_in()
        data = {
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=7)).isoformat(),
            "adults": "1",
            "children": "0",
            "remarks": "",
            "promo_code": "",
        }

        with mock.patch("orders.services.placing._create_order", side_effect=create):
            response = submit_order(self.client, self.url, data)

        self.assertRedirects(response, reverse("my_orders"))
        self.assertEqual(Order.objects.count(), MAX_ORDERS_PER_DAY)


class PlaceOrderServiceValidationTests(TestCase):
    """Le service revérifie les règles, même sans passer par le formulaire."""

    def setUp(self):
        self.marie = create_client()
        self.country = create_country()
        self.destination = create_destination(self.country, "Kyoto")

    def data(self, **fields):
        data = {
            "departure_date": departure_in(),
            "return_date": departure_in() + timedelta(days=7),
            "adults": 2,
            "children": 0,
            "remarks": "",
            "activities": [],
        }
        data.update(fields)
        return data

    def assert_refused(self, data):
        with self.assertRaises(ValidationError):
            place_order(self.marie, self.destination, data)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(StatusChange.objects.exists())

    def test_valid_order_placed(self):
        order = place_order(self.marie, self.destination, self.data(activities=[create_activity(self.country)]))

        self.assertEqual(order.activities.count(), 1)

    def test_departure_too_soon_refused(self):
        self.assert_refused(self.data(departure_date=departure_in(1), return_date=departure_in(5)))

    def test_too_many_travellers_refused(self):
        self.assert_refused(self.data(adults=6, children=5))

    def test_activity_of_another_country_refused(self):
        self.assert_refused(self.data(activities=[create_activity(create_country("Pérou"))]))

    def test_inactive_activity_refused(self):
        self.assert_refused(self.data(activities=[create_activity(self.country, active=False)]))


class EmailConfirmationRequiredTests(TestCase):
    """Adresse e-mail non confirmée : pas de demande de voyage (vue et service)."""

    def setUp(self):
        self.marie = create_client(email_confirmed_at=None)
        self.destination = create_destination(create_country(), "Kyoto")
        self.data = {
            "departure_date": departure_in(),
            "return_date": departure_in() + timedelta(days=7),
            "adults": 2,
            "children": 0,
            "remarks": "",
            "activities": [],
        }

    def test_view_refuses_and_offers_new_link(self):
        self.client.force_login(self.marie)
        url = reverse("create_order", args=[self.destination.pk])

        response = self.client.post(url, {**self.data, "confirm": ""}, follow=True)

        self.assertRedirects(response, reverse("resend_confirmation"))
        self.assertContains(response, "confirmez d&#x27;abord votre adresse e-mail")
        self.assertContains(response, "Renvoyer le lien")
        self.assertFalse(Order.objects.exists())

    def test_service_refuses_before_confirmation(self):
        with self.assertRaises(placing.EmailNotConfirmed):
            place_order(self.marie, self.destination, self.data)
        self.assertFalse(Order.objects.exists())

    def test_allowed_after_confirmation(self):
        confirm(self.marie)

        self.assertEqual(place_order(self.marie, self.destination, self.data).client, self.marie)
