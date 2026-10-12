from datetime import date, datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.tests.factories import create_client
from catalog.tests.factories import create_country, create_destination
from dashboard.forms import PeriodForm
from dashboard.services.periods import DateBasis, Shortcut, custom_period, shortcut_period
from orders.models import Order
from orders.tests.factories import create_order


def bounds(period) -> tuple:
    return period.start, period.end


class ShortcutTests(SimpleTestCase):
    def test_bounds_and_previous_period(self):
        today = date(2026, 5, 20)
        cases = {
            Shortcut.THIS_MONTH: ((date(2026, 5, 1), date(2026, 5, 31)), (date(2026, 4, 1), date(2026, 4, 30))),
            Shortcut.LAST_MONTH: ((date(2026, 4, 1), date(2026, 4, 30)), (date(2026, 3, 1), date(2026, 3, 31))),
            Shortcut.THIS_QUARTER: ((date(2026, 4, 1), date(2026, 6, 30)), (date(2026, 1, 1), date(2026, 3, 31))),
            Shortcut.THIS_YEAR: ((date(2026, 1, 1), date(2026, 12, 31)), (date(2025, 1, 1), date(2025, 12, 31))),
            Shortcut.LAST_12_MONTHS: ((date(2025, 6, 1), date(2026, 5, 31)), (date(2024, 6, 1), date(2025, 5, 31))),
        }
        for shortcut, (expected, expected_previous) in cases.items():
            with self.subTest(shortcut=shortcut):
                period = shortcut_period(shortcut, today=today)

                self.assertEqual(bounds(period), expected)
                self.assertEqual(bounds(period.previous()), expected_previous)

    def test_january_goes_back_to_december_of_previous_year(self):
        january = shortcut_period(Shortcut.THIS_MONTH, today=date(2026, 1, 15))
        last_month = shortcut_period(Shortcut.LAST_MONTH, today=date(2026, 1, 15))

        self.assertEqual(bounds(january.previous()), (date(2025, 12, 1), date(2025, 12, 31)))
        self.assertEqual(bounds(last_month), (date(2025, 12, 1), date(2025, 12, 31)))

    def test_quarters(self):
        cases = {
            date(2026, 1, 1): date(2026, 1, 1),
            date(2026, 3, 31): date(2026, 1, 1),
            date(2026, 8, 15): date(2026, 7, 1),
            date(2026, 12, 31): date(2026, 10, 1),
        }
        for today, start in cases.items():
            with self.subTest(today=today):
                self.assertEqual(shortcut_period(Shortcut.THIS_QUARTER, today=today).start, start)
        first_quarter = shortcut_period(Shortcut.THIS_QUARTER, today=date(2026, 2, 10))
        self.assertEqual(bounds(first_quarter.previous()), (date(2025, 10, 1), date(2025, 12, 31)))

    def test_month_compared_with_whole_previous_month(self):
        # Mars (31 jours) est comparé à février entier (28 jours), pas aux 31 jours d'avant.
        march = shortcut_period(Shortcut.THIS_MONTH, today=date(2026, 3, 10))

        self.assertEqual(bounds(march.previous()), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_custom_period_compared_with_same_number_of_days(self):
        period = custom_period(date(2026, 3, 1), date(2026, 3, 10))

        self.assertEqual(bounds(period.previous()), (date(2026, 2, 19), date(2026, 2, 28)))

    def test_compared_to_text(self):
        today = date(2026, 5, 20)
        cases = {
            Shortcut.THIS_MONTH: "par rapport au mois dernier",
            Shortcut.THIS_YEAR: "par rapport à l'année dernière",
            Shortcut.LAST_12_MONTHS: "par rapport aux 12 mois précédents",
        }
        for shortcut, text in cases.items():
            with self.subTest(shortcut=shortcut):
                self.assertEqual(shortcut_period(shortcut, today=today).compared_to, text)
        self.assertEqual(custom_period(today, today).compared_to, "par rapport à la période précédente")


class FilterOrdersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        client = create_client()
        destination = create_destination(create_country())
        # Heure de Bruxelles : 23 h 30 le 31 mars, puis 0 h 30 le 1er avril (le 31 mars en UTC toutes les deux).
        cls.march_order = create_order(
            client,
            destination,
            created_at=timezone.make_aware(datetime(2026, 3, 31, 23, 30)),
            departure_date=date(2026, 6, 1),
        )
        cls.april_order = create_order(
            client,
            destination,
            created_at=timezone.make_aware(datetime(2026, 4, 1, 0, 30)),
            departure_date=date(2026, 7, 1),
        )

    def orders_in(self, period) -> set:
        return set(period.filter_orders(Order.objects.all()))

    def test_by_order_date_uses_brussels_days(self):
        march = custom_period(date(2026, 3, 1), date(2026, 3, 31))
        april = custom_period(date(2026, 4, 1), date(2026, 4, 30))

        self.assertEqual(self.orders_in(march), {self.march_order})
        self.assertEqual(self.orders_in(april), {self.april_order})

    def test_by_departure_date_bounds_included(self):
        june_to_july_first = custom_period(date(2026, 6, 1), date(2026, 7, 1), DateBasis.DEPARTURE)
        june = custom_period(date(2026, 6, 1), date(2026, 6, 30), DateBasis.DEPARTURE)

        self.assertEqual(self.orders_in(june_to_july_first), {self.march_order, self.april_order})
        self.assertEqual(self.orders_in(june), {self.march_order})


class PeriodFormTests(SimpleTestCase):
    def test_custom_period(self):
        form = PeriodForm(
            {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.DEPARTURE, "start": "2026-03-01", "end": "2026-03-10"}
        )

        period = form.period()

        self.assertEqual(bounds(period), (date(2026, 3, 1), date(2026, 3, 10)))
        self.assertEqual(period.basis, DateBasis.DEPARTURE)

    def test_dates_ignored_for_a_shortcut(self):
        form = PeriodForm({"shortcut": Shortcut.THIS_YEAR, "basis": DateBasis.ORDERED, "end": "2026-03-10"})

        self.assertEqual(form.period(), shortcut_period(Shortcut.THIS_YEAR))

    def test_invalid_custom_period_falls_back_to_this_month(self):
        cases = {
            "fin manquante": ({"start": "2026-03-01"}, "Obligatoire pour une période personnalisée."),
            "fin avant le début": (
                {"start": "2026-03-10", "end": "2026-03-01"},
                "La fin de la période doit être après son début.",
            ),
            "plus de 5 ans": ({"start": "2020-01-01", "end": "2025-01-31"}, "La période ne peut pas dépasser 5 ans."),
        }
        for case, (dates, error) in cases.items():
            with self.subTest(case):
                form = PeriodForm({"shortcut": Shortcut.CUSTOM, "basis": DateBasis.DEPARTURE, **dates})

                self.assertEqual(form.period(), shortcut_period(Shortcut.THIS_MONTH))
                self.assertEqual(form.errors["end"], [error])
