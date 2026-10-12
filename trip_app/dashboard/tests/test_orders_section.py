from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from common.text import NBSP
from dashboard.services.orders_section import order_figures, orders_section
from dashboard.services.periods import custom_period
from orders.models import OrderStatus, StatusChange
from orders.tests.factories import create_order

MARCH = custom_period(date(2026, 3, 1), date(2026, 3, 31))


def march(day: int, hour: int = 10) -> datetime:
    return timezone.make_aware(datetime(2026, 3, day, hour))


class OrdersSectionTests(TestCase):
    def setUp(self):
        self.kyoto = create_destination(create_country())
        self.marie = create_client()
        self.agent = create_agent()

    def add_order(self, status=OrderStatus.PENDING, created_at=None, **fields):
        return create_order(self.marie, self.kyoto, status=status, created_at=created_at or march(10), **fields)

    def decide(self, order, status, after: timedelta, by_client=False):
        StatusChange.objects.create(
            order=order,
            status=status,
            changed_at=order.created_at + after,
            author_name="Marie" if by_client else "Agent",
            author=self.marie if by_client else self.agent,
            by_client=by_client,
        )

    def test_counts_and_amounts(self):
        self.add_order(estimated_price=Decimal("1000"), discount=Decimal("50"))
        # Prix et remise recalculés à la confirmation : ils remplacent l'estimation de départ.
        self.add_order(
            OrderStatus.CONFIRMED,
            estimated_price=Decimal("2000"),
            discount=Decimal("100"),
            confirmed_price=Decimal("2200"),
            confirmed_discount=Decimal("120"),
        )
        self.add_order(OrderStatus.CANCELLED, estimated_price=Decimal("700"), discount=Decimal("30"))
        self.add_order(OrderStatus.CANCELLED, estimated_price=Decimal("300"))
        self.add_order(created_at=march(10) - timedelta(days=20))  # hors période

        figures = order_figures(MARCH)

        self.assertEqual(
            (figures.pending_count, figures.confirmed_count, figures.cancelled_count, figures.total_count),
            (1, 1, 2, 4),
        )
        self.assertEqual(figures.confirmed_amount, Decimal("2200"))
        self.assertEqual(figures.pending_amount, Decimal("1000"))
        # Les annulées sont à part : ni dans le montant confirmé ni dans les remises.
        self.assertEqual(figures.cancelled_amount, Decimal("1000"))
        self.assertEqual(figures.total_discount, Decimal("170"))
        self.assertEqual(figures.confirmation_rate, Decimal("25.0"))
        self.assertEqual(figures.cancellation_rate, Decimal("50.0"))

    def test_no_order_gives_no_rate(self):
        section = orders_section(MARCH)

        self.assertIsNone(section.cancellation_rate)
        self.assertIsNone(section.processed_within_48h_rate)
        rates = [figure for figure in section.counts if figure.label.startswith("Taux")]
        self.assertEqual([(figure.value, figure.comparison.text) for figure in rates], [("—", "—")] * 2)

    def test_processing_delay_counts_staff_decisions_only(self):
        quick = self.add_order(OrderStatus.CONFIRMED)
        self.decide(quick, OrderStatus.CONFIRMED, timedelta(hours=10))
        # Seule la première décision compte.
        self.decide(quick, OrderStatus.CANCELLED, timedelta(hours=100))
        exactly_48h = self.add_order(OrderStatus.CANCELLED)
        self.decide(exactly_48h, OrderStatus.CANCELLED, timedelta(hours=48))
        slow = self.add_order(OrderStatus.CONFIRMED)
        self.decide(slow, OrderStatus.CONFIRMED, timedelta(days=3, hours=2))
        # Annulée par le client : pas un traitement de l'agence.
        by_client = self.add_order(OrderStatus.CANCELLED)
        self.decide(by_client, OrderStatus.CANCELLED, timedelta(hours=1), by_client=True)
        self.add_order()  # encore en attente

        figures = order_figures(MARCH)

        self.assertEqual(figures.average_delay, timedelta(hours=44))
        self.assertEqual(figures.longest_delay, timedelta(days=3, hours=2))
        self.assertEqual(figures.processed_within_48h_rate, Decimal("66.7"))
        delays = {figure.label: figure.value for figure in orders_section(MARCH).delays}
        self.assertEqual(delays["Délai moyen de traitement"], f"1{NBSP}j 20{NBSP}h")
        self.assertEqual(delays["Délai le plus long"], f"3{NBSP}j 2{NBSP}h")
        self.assertEqual(delays["Commandes traitées en moins de 48 h"], f"67{NBSP}%")

    def test_compared_with_previous_period(self):
        february = march(10) - timedelta(days=20)
        for _ in range(2):
            self.add_order(OrderStatus.CANCELLED, created_at=february)
        self.add_order(OrderStatus.CONFIRMED, created_at=february)
        for _ in range(3):
            self.add_order(OrderStatus.CANCELLED)

        section = orders_section(MARCH)

        cancelled = next(figure for figure in section.counts if figure.label == "Commandes annulées")
        self.assertEqual((cancelled.comparison.text, cancelled.comparison.tone), (f"+50{NBSP}%", "bad"))
        confirmed = next(figure for figure in section.counts if figure.label == "Commandes confirmées")
        self.assertEqual(confirmed.comparison.tone, "bad")

    def test_overdue_pending_orders_counted_whatever_the_period(self):
        self.add_order(created_at=timezone.now() - timedelta(hours=49))
        self.add_order(created_at=timezone.now() - timedelta(hours=47))
        self.add_order(OrderStatus.CONFIRMED, created_at=timezone.now() - timedelta(hours=100))

        self.assertEqual(orders_section(MARCH).overdue_pending_count, 1)

    def test_shown_on_dashboard(self):
        cache.clear()
        self.add_order(OrderStatus.CONFIRMED, created_at=timezone.now(), estimated_price=Decimal("1234.50"))
        self.client.force_login(create_admin())

        response = self.client.get(reverse("pilotage_dashboard"))

        self.assertContains(response, "Montant estimé des commandes confirmées")
        self.assertContains(response, f"1{NBSP}234,50{NBSP}€")
        self.assertContains(response, "ce n'est pas de l'argent encaissé")
