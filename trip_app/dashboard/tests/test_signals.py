from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_client
from catalog.tests.factories import create_country, create_destination
from common.text import NBSP
from dashboard.models import SignalThresholds
from dashboard.services.orders_section import OrdersSection
from dashboard.services.signals import active_signals
from orders.tests.factories import create_order

# L'accès (administrateur seulement) est vérifié par la matrice d'accès (config/test_access.py).


def section(cancellation_rate=None, overdue_pending_count=0, processed_within_48h_rate=None) -> OrdersSection:
    return OrdersSection(
        counts=[],
        amounts=[],
        cancelled_amount=None,
        delays=[],
        cancellation_rate=cancellation_rate,
        processed_within_48h_rate=processed_within_48h_rate,
        overdue_pending_count=overdue_pending_count,
    )


class ActiveSignalsTests(SimpleTestCase):
    # Seuils d'origine : 25 %, 5 commandes, 80 %.
    thresholds = SignalThresholds()

    def signals(self, **figures) -> list[str]:
        return active_signals(section(**figures), self.thresholds)

    def test_cancellation_rate_above_threshold(self):
        self.assertEqual(self.signals(cancellation_rate=Decimal("25.0")), [])
        self.assertEqual(
            self.signals(cancellation_rate=Decimal("25.1")),
            [f"Taux d'annulation : 25,1{NBSP}% (seuil : 25{NBSP}%)"],
        )

    def test_overdue_pending_above_threshold(self):
        self.assertEqual(self.signals(overdue_pending_count=5), [])
        self.assertEqual(
            self.signals(overdue_pending_count=6), ["Commandes en attente depuis plus de 48 h : 6 (seuil : 5)"]
        )

    def test_processed_within_48h_rate_below_threshold(self):
        self.assertEqual(self.signals(processed_within_48h_rate=Decimal("80.0")), [])
        self.assertEqual(
            self.signals(processed_within_48h_rate=Decimal("79.9")),
            [f"Commandes traitées en moins de 48 h : 79,9{NBSP}% (seuil : 80{NBSP}%)"],
        )

    def test_missing_rates_give_no_signal(self):
        self.assertEqual(self.signals(cancellation_rate=None, processed_within_48h_rate=None), [])


class SignalsPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = create_admin()
        self.client.force_login(self.admin)

    def test_changed_threshold_applies_without_clearing_cache(self):
        create_order(
            create_client(), create_destination(create_country()), created_at=timezone.now() - timedelta(days=3)
        )
        response = self.client.get(reverse("pilotage_dashboard"))
        self.assertContains(response, "Aucun signal : tous les indicateurs sont dans les seuils.")

        SignalThresholds.objects.filter(pk=1).update(max_overdue_pending=0)

        response = self.client.get(reverse("pilotage_dashboard"))
        self.assertContains(response, "Commandes en attente depuis plus de 48 h : 1 (seuil : 0)")

    def test_saves_thresholds_and_author(self):
        response = self.client.post(
            reverse("signal_thresholds"),
            {"max_cancellation_rate": 30, "max_overdue_pending": 8, "min_processed_within_48h_rate": 70},
        )

        self.assertRedirects(response, reverse("pilotage_dashboard"))
        thresholds = SignalThresholds.current()
        self.assertEqual(
            (thresholds.max_cancellation_rate, thresholds.max_overdue_pending, thresholds.min_processed_within_48h_rate),
            (30, 8, 70),
        )
        self.assertEqual(thresholds.updated_by, self.admin)
        self.assertEqual(thresholds.updated_by_name, "Anne Durand")

    def test_rejects_out_of_range_values(self):
        response = self.client.post(
            reverse("signal_thresholds"),
            {"max_cancellation_rate": 101, "max_overdue_pending": -1, "min_processed_within_48h_rate": -1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.context["form"].errors),
            {"max_cancellation_rate", "max_overdue_pending", "min_processed_within_48h_rate"},
        )
        self.assertEqual(SignalThresholds.current().max_cancellation_rate, 25)
