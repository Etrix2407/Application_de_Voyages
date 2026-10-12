from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Order, OrderStatus
from orders.tests.factories import create_order
from reviews.models import ReviewStatus
from reviews.tests.factories import create_review, create_trip_done

# L'accès (personnel seulement, jamais les clients) est vérifié par la matrice d'accès (config/test_access.py).


class OperationalDashboardTests(TestCase):
    url = reverse("operational_dashboard")

    def setUp(self):
        self.client.force_login(create_agent())
        self.marie = create_client()
        self.kyoto = create_destination(create_country(), "Kyoto")

    def order(self, status=OrderStatus.PENDING, hours_ago=1, departure_in_days=60):
        order = create_order(
            self.marie,
            self.kyoto,
            status=status,
            departure_date=timezone.localdate() + timedelta(days=departure_in_days),
            estimated_price=Decimal("4321"),
        )
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))
        return order

    def listed(self, url):
        return {order.pk for order in self.client.get(url).context["page"].object_list}

    def test_pending_and_overdue_orders(self):
        recent = self.order(hours_ago=47)
        overdue = self.order(hours_ago=49)
        self.order(status=OrderStatus.CONFIRMED, hours_ago=72)

        response = self.client.get(self.url)
        figures = response.context["figures"]

        self.assertEqual(figures.pending.count, 2)
        self.assertEqual(figures.overdue.count, 1)
        self.assertTrue(response.context["overdue_alert"])
        self.assertEqual(self.listed(response.context["pending_url"]), {recent.pk, overdue.pk})
        self.assertEqual(self.listed(response.context["overdue_url"]), {overdue.pk})

    def test_overdue_not_red_when_zero(self):
        self.order(hours_ago=47)

        response = self.client.get(self.url)

        self.assertFalse(response.context["overdue_alert"])
        self.assertNotContains(response, "key-figure-alert")

    def test_departures_of_the_week_confirmed_only(self):
        today = self.order(status=OrderStatus.CONFIRMED, departure_in_days=0)
        last_day = self.order(status=OrderStatus.CONFIRMED, departure_in_days=6)
        self.order(status=OrderStatus.CONFIRMED, departure_in_days=7)
        self.order(status=OrderStatus.PENDING, departure_in_days=3)
        self.order(status=OrderStatus.CANCELLED, departure_in_days=3)

        response = self.client.get(self.url)

        self.assertEqual(response.context["figures"].departures.count, 2)
        self.assertEqual(self.listed(response.context["departures_url"]), {today.pk, last_day.pk})

    def test_reviews_to_moderate(self):
        create_review(create_trip_done(self.marie, self.kyoto))
        create_review(create_trip_done(self.marie, self.kyoto), status=ReviewStatus.PUBLISHED)

        response = self.client.get(self.url)

        self.assertEqual(response.context["figures"].reviews_to_moderate, 1)
        self.assertContains(response, reverse("manage_pending_reviews"))

    def test_no_amount_shown(self):
        self.order(status=OrderStatus.CONFIRMED, departure_in_days=2)

        response = self.client.get(self.url)

        self.assertNotContains(response, "4321")
        self.assertNotContains(response, "4 321")
        self.assertNotContains(response, "€")

    def test_menu_link_for_staff(self):
        self.assertContains(self.client.get(reverse("home")), self.url)
