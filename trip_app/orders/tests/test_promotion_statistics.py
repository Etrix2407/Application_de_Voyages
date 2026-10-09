from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Status
from orders.services.promotion_statistics import promotion_statistics
from promotions.tests.factories import create_promotion

from .factories import create_order


class PromotionStatisticsTests(TestCase):
    def setUp(self):
        self.promotion = create_promotion()
        self.kyoto = create_destination(create_country())
        self.marie = create_client()
        self.paul = create_client(email="paul@example.com", first_name="Paul")

    def add_order(self, client, discount="50", **fields):
        return create_order(client, self.kyoto, promotion=self.promotion, discount=Decimal(discount), **fields)

    def test_figures(self):
        self.add_order(self.marie, discount="50")
        # Confirmée : la remise recalculée à la confirmation remplace celle de la demande.
        self.add_order(self.marie, discount="50", status=Status.CONFIRMED, confirmed_discount=Decimal("60"))
        self.add_order(self.paul, discount="30")
        self.add_order(None, discount="20")
        create_order(self.paul, self.kyoto, discount=Decimal("99"))  # autre demande, sans cette promotion

        statistics = promotion_statistics(self.promotion)

        self.assertEqual(statistics.order_count, 4)
        self.assertEqual(statistics.total_discount, Decimal("160.00"))
        self.assertEqual(statistics.client_count, 2)
        self.assertEqual(statistics.anonymized_count, 1)

    def test_cancelled_orders_excluded_from_all_figures(self):
        kept = self.add_order(self.marie)
        cancelled = self.add_order(self.paul, status=Status.CANCELLED)

        statistics = promotion_statistics(self.promotion)

        self.assertEqual(statistics.order_count, 1)
        self.assertEqual(statistics.total_discount, Decimal("50.00"))
        self.assertEqual(statistics.client_count, 1)
        self.assertEqual(list(statistics.orders), [kept])
        self.assertEqual(list(statistics.cancelled_orders), [cancelled])

    def test_unused_promotion(self):
        statistics = promotion_statistics(self.promotion)

        self.assertEqual(statistics.order_count, 0)
        self.assertEqual(statistics.total_discount, Decimal("0.00"))

    def test_page_for_staff(self):
        order = self.add_order(self.marie, discount="50")
        self.client.force_login(create_agent())

        response = self.client.get(reverse("manage_promotion_statistics", args=[self.promotion.pk]))

        self.assertContains(response, "50,00 €")
        self.assertContains(response, reverse("manage_order_detail", args=[order.pk]))
        self.assertContains(response, "Aucune demande annulée.")
