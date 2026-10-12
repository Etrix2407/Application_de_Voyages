from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin
from catalog.tests.factories import create_activity, create_country, create_destination
from dashboard.services.periods import custom_period
from dashboard.services.rankings import build_rankings
from orders.models import OrderStatus
from orders.tests.factories import create_order

CONFIRMED, PENDING, CANCELLED = OrderStatus.CONFIRMED, OrderStatus.PENDING, OrderStatus.CANCELLED


def this_week():
    today = timezone.localdate()
    return custom_period(today - timedelta(days=3), today + timedelta(days=3))


def order(destination, status=CONFIRMED, count=1, **fields):
    for _ in range(count):
        create_order(None, destination, status=status, **fields)


class TopDestinationsAndCountriesTests(TestCase):
    def setUp(self):
        self.japan = create_country("Japon")

    def test_five_most_confirmed_ties_broken_by_name(self):
        for name, count in [("Osaka", 1), ("Kyoto", 3), ("Nara", 2), ("Tokyo", 2), ("Kobe", 4), ("Sapporo", 1)]:
            order(create_destination(self.japan, name), count=count)

        names = [item.name for item in build_rankings(this_week()).destinations]

        self.assertEqual(names, ["Kobe", "Kyoto", "Nara", "Tokyo", "Osaka"])

    def test_only_confirmed_orders_count(self):
        peru = create_country("Pérou", time_zone="America/Lima")
        kyoto = create_destination(self.japan, "Kyoto")
        cusco = create_destination(peru, "Cusco")
        order(kyoto)
        order(cusco, count=2)
        order(kyoto, status=PENDING, count=3)
        order(kyoto, status=CANCELLED, count=3)

        rankings = build_rankings(this_week())

        self.assertEqual([(i.name, i.order_count) for i in rankings.destinations], [("Cusco", 2), ("Kyoto", 1)])
        self.assertEqual([(i.name, i.order_count) for i in rankings.countries], [("Pérou", 2), ("Japon", 1)])

    def test_estimated_amount_is_the_latest_price(self):
        kyoto = create_destination(self.japan, "Kyoto")
        order(kyoto, estimated_price=Decimal("1000.00"))
        order(kyoto, estimated_price=Decimal("1000.00"), confirmed_price=Decimal("1200.50"))
        order(kyoto, status=PENDING, estimated_price=Decimal("5000.00"))

        rankings = build_rankings(this_week())

        self.assertEqual(rankings.destinations[0].estimated_amount, Decimal("2200.50"))
        self.assertEqual(rankings.countries[0].estimated_amount, Decimal("2200.50"))


class TopActivitiesTests(TestCase):
    def test_five_most_chosen_in_orders_not_cancelled(self):
        japan = create_country("Japon")
        kyoto = create_destination(japan, "Kyoto")
        tea, karaoke, sumo, onsen, temple, garden = (
            create_activity(japan, name)
            for name in ("Thé", "Karaoké", "Sumo", "Onsen", "Temple", "Jardin")
        )
        order(kyoto, activities=[tea, karaoke, sumo, onsen, temple, garden])
        order(kyoto, status=PENDING, activities=[tea, karaoke])
        order(kyoto, activities=[tea])
        order(kyoto, status=CANCELLED, count=3, activities=[garden])

        names = [(item.name, item.order_count) for item in build_rankings(this_week()).activities]

        self.assertEqual(names, [("Thé", 3), ("Karaoké", 2), ("Jardin", 1), ("Onsen", 1), ("Sumo", 1)])


class LeastRequestedTests(TestCase):
    def test_active_destinations_with_fewest_orders_zero_included(self):
        japan = create_country("Japon")
        closed = create_country("Islande", active=False)
        create_destination(closed, "Reykjavik")
        create_destination(japan, "Hakone", active=False)
        for name, count in [("Kyoto", 3), ("Nara", 1), ("Osaka", 2), ("Kobe", 1), ("Tokyo", 4)]:
            order(create_destination(japan, name), count=count)
        create_destination(japan, "Sapporo")
        order(create_destination(japan, "Nikko"), status=CANCELLED, count=5)

        items = [(item.name, item.order_count) for item in build_rankings(this_week()).least_requested]

        self.assertEqual(items, [("Nikko", 0), ("Sapporo", 0), ("Kobe", 1), ("Nara", 1), ("Osaka", 2)])


class RankingsPageTests(TestCase):
    def test_tables_link_to_management_pages(self):
        cache.clear()
        kyoto = create_destination(create_country("Japon"), "Kyoto")
        order(kyoto)
        self.client.force_login(create_admin())

        response = self.client.get(reverse("pilotage_dashboard"))

        self.assertContains(response, reverse("manage_edit_destination", args=[kyoto.pk]))
        self.assertContains(response, reverse("manage_country", args=[kyoto.country_id]))
        self.assertContains(response, "Aucune activité choisie sur cette période.")
