from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.models import Activity, Destination
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import (
    MAX_DAYS_BEFORE_DEPARTURE,
    MAX_REMARKS_LENGTH,
    MAX_STAY_DAYS,
    MAX_TRAVELLERS,
    MIN_DAYS_BEFORE_DEPARTURE,
    Order,
    OrderActivity,
    Status,
    StatusChange,
)
from orders.services.placing import place_order
from orders.services.pricing import estimate_price

from .factories import create_order, departure_in


class EstimatePriceTests(SimpleTestCase):
    def test_formula_with_children_at_half_price(self):
        # (1000 + 50 + 30) × 2 adultes + (1000 + 50 + 30) × 50 % × 2 enfants
        price = estimate_price(Decimal("1000"), [Decimal("50"), Decimal("30")], adults=2, children=2)

        self.assertEqual(price, Decimal("3240.00"))

    def test_children_half_price_applies_to_activities(self):
        self.assertEqual(estimate_price(None, [Decimal("40")], adults=0, children=1), Decimal("20.00"))

    def test_destination_on_quote_counts_activities_only(self):
        self.assertEqual(estimate_price(None, [Decimal("25")], adults=2, children=0), Decimal("50.00"))

    def test_no_activity(self):
        self.assertEqual(estimate_price(Decimal("450"), [], adults=1, children=0), Decimal("450.00"))

    def test_rounded_to_the_cent(self):
        self.assertEqual(estimate_price(Decimal("10.01"), [], adults=0, children=1), Decimal("5.01"))


class OrderValidationTests(TestCase):
    def setUp(self):
        self.client_user = create_client()
        self.destination = create_destination(create_country(), price_from=Decimal("1200"))

    def new_order(self, **fields):
        fields.setdefault("departure_date", departure_in())
        fields.setdefault("return_date", fields["departure_date"] + timedelta(days=7))
        fields.setdefault("adults", 2)
        fields.setdefault("estimated_price", Decimal("0"))
        return Order(
            client=self.client_user,
            destination=self.destination,
            destination_name=self.destination.name,
            country_name=self.destination.country.name,
            **fields,
        )

    def assert_invalid(self, order, field):
        with self.assertRaises(ValidationError) as error:
            order.full_clean()
        self.assertIn(field, error.exception.message_dict)

    def test_valid_order(self):
        self.new_order().full_clean()

    def test_return_must_be_after_departure(self):
        departure = departure_in()
        for return_date in [departure, departure - timedelta(days=1)]:
            with self.subTest(return_date=return_date):
                self.assert_invalid(self.new_order(departure_date=departure, return_date=return_date), "return_date")

    def test_departure_at_least_seven_days_ahead(self):
        too_soon = departure_in(MIN_DAYS_BEFORE_DEPARTURE - 1)
        self.assert_invalid(self.new_order(departure_date=too_soon), "departure_date")
        self.new_order(departure_date=departure_in(MIN_DAYS_BEFORE_DEPARTURE)).full_clean()

    def test_departure_within_two_years(self):
        self.new_order(departure_date=departure_in(MAX_DAYS_BEFORE_DEPARTURE)).full_clean()
        too_late = departure_in(MAX_DAYS_BEFORE_DEPARTURE + 1)
        self.assert_invalid(self.new_order(departure_date=too_late), "departure_date")

    def test_stay_at_most_ninety_days(self):
        departure = departure_in()
        self.new_order(departure_date=departure, return_date=departure + timedelta(days=MAX_STAY_DAYS)).full_clean()
        self.assert_invalid(
            self.new_order(departure_date=departure, return_date=departure + timedelta(days=MAX_STAY_DAYS + 1)),
            "return_date",
        )

    def test_remarks_length_limited(self):
        self.new_order(remarks="a" * MAX_REMARKS_LENGTH).full_clean()
        self.assert_invalid(self.new_order(remarks="a" * (MAX_REMARKS_LENGTH + 1)), "remarks")

    def test_at_least_one_adult(self):
        self.assert_invalid(self.new_order(adults=0, children=2), "adults")

    def test_at_most_ten_travellers(self):
        self.new_order(adults=6, children=MAX_TRAVELLERS - 6).full_clean()
        self.assert_invalid(self.new_order(adults=6, children=MAX_TRAVELLERS - 5), "children")

    def test_inactive_destination_cannot_be_ordered(self):
        self.destination.active = False
        self.destination.save()

        self.assert_invalid(self.new_order(), "destination")

    def test_existing_order_stays_valid_when_destination_deactivated_or_time_passes(self):
        order = create_order(self.client_user, self.destination)
        self.destination.active = False
        self.destination.save()
        order.departure_date = departure_in(1)
        order.return_date = order.departure_date + timedelta(days=3)

        order.full_clean()

    def test_activity_must_be_in_destination_country(self):
        order = create_order(self.client_user, self.destination)
        elsewhere = create_activity(create_country("Pérou"))
        line = OrderActivity(order=order, activity=elsewhere, activity_name=elsewhere.name, unit_price=Decimal("10"))

        with self.assertRaises(ValidationError):
            line.full_clean()


class FrozenDataTests(TestCase):
    def setUp(self):
        self.country = create_country()
        self.destination = create_destination(self.country, price_from=Decimal("1200"))
        self.activity = create_activity(self.country, price_per_person=Decimal("45"))
        self.order = create_order(create_client(), self.destination, [self.activity])

    def test_prices_frozen_when_catalog_prices_change(self):
        Destination.objects.filter(pk=self.destination.pk).update(price_from=Decimal("9999"))
        Activity.objects.filter(pk=self.activity.pk).update(price_per_person=Decimal("9999"))

        self.order.refresh_from_db()
        self.assertEqual(self.order.destination_price, Decimal("1200"))
        self.assertEqual(self.order.activities.get().unit_price, Decimal("45"))

    def test_destination_without_price_is_on_quote(self):
        order = create_order(create_client("autre@example.com"), create_destination(self.country, "Sans prix"))

        self.assertTrue(order.is_quote_required)
        self.assertFalse(self.order.is_quote_required)

    def test_deleting_client_keeps_anonymous_order(self):
        self.order.client.delete()

        self.order.refresh_from_db()
        self.assertIsNone(self.order.client)

    def test_history_keeps_author_name_after_agent_deletion(self):
        agent = create_agent()
        change = StatusChange.objects.create(
            order=self.order, status=Status.CONFIRMED, author=agent, author_name=agent.get_full_name()
        )
        agent.delete()

        change.refresh_from_db()
        self.assertIsNone(change.author)
        self.assertEqual(change.author_name, "Luc Martin")


class OrderedCatalogItemProtectionTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        country = create_country()
        self.destination = create_destination(country)
        self.activity = create_activity(country, destination=self.destination)
        create_order(create_client(), self.destination, [self.activity])

    def test_ordered_destination_cannot_be_deleted(self):
        response = self.client.post(
            reverse("manage_delete_destination", args=[self.destination.pk]), follow=True
        )

        self.assertContains(response, "utilisé dans des demandes de voyage")
        self.assertTrue(Destination.objects.filter(pk=self.destination.pk).exists())

    def test_ordered_activity_cannot_be_deleted(self):
        response = self.client.post(reverse("manage_delete_activity", args=[self.activity.pk]), follow=True)

        self.assertContains(response, "utilisé dans des demandes de voyage")
        self.assertTrue(Activity.objects.filter(pk=self.activity.pk).exists())

    def test_unordered_items_can_still_be_deleted(self):
        other = create_destination(self.destination.country, "Libre")

        self.client.post(reverse("manage_delete_destination", args=[other.pk]))

        self.assertFalse(Destination.objects.filter(pk=other.pk).exists())


class FrozenNamesTests(TestCase):
    """Comme les prix, les noms sont ceux du jour de la demande."""

    def setUp(self):
        self.marie = create_client()
        self.country = create_country("Japon")
        self.destination = create_destination(self.country, "Kyoto")
        self.tea = create_activity(self.country, "Cérémonie du thé")
        self.order = place_order(
            self.marie,
            self.destination,
            {
                "departure_date": departure_in(),
                "return_date": departure_in() + timedelta(days=7),
                "adults": 2,
                "children": 0,
                "remarks": "",
                "activities": [self.tea],
            },
        )

    def rename_catalog(self):
        self.country.name = "Nippon"
        self.country.save()
        self.destination.name = "Kyōto (ancienne capitale)"
        self.destination.save()
        self.tea.name = "Atelier thé matcha"
        self.tea.save()

    def test_service_copies_names(self):
        self.assertEqual((self.order.destination_name, self.order.country_name), ("Kyoto", "Japon"))
        self.assertEqual(self.order.activities.get().activity_name, "Cérémonie du thé")

    def test_renaming_catalog_does_not_change_orders(self):
        self.rename_catalog()

        for user, url in [
            (self.marie, reverse("my_order_detail", args=[self.order.pk])),
            (create_agent(), reverse("manage_order_detail", args=[self.order.pk])),
        ]:
            with self.subTest(url=url):
                self.client.force_login(user)
                response = self.client.get(url)

                self.assertContains(response, "Kyoto (Japon)")
                self.assertContains(response, "Cérémonie du thé")
                self.assertNotContains(response, "Nippon")
                self.assertNotContains(response, "matcha")

    def test_lists_show_frozen_names(self):
        self.rename_catalog()
        self.client.force_login(self.marie)

        self.assertContains(self.client.get(reverse("my_orders")), "Kyoto (Japon)")
