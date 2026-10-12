from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_admin
from catalog.tests.factories import create_country, create_destination
from common.text import NBSP
from dashboard.services.charts import (
    BAR_MAX_WIDTH,
    OTHER_COUNTRIES,
    country_chart,
    monthly_chart,
    status_chart,
)
from dashboard.services.periods import DateBasis, Shortcut, custom_period
from orders.models import OrderStatus
from orders.tests.factories import create_order

BRUSSELS = ZoneInfo("Europe/Brussels")


def brussels(*args) -> datetime:
    return datetime(*args, tzinfo=BRUSSELS)


class ChartTestCase(TestCase):
    def setUp(self):
        self.japan = create_country("Japon")
        self.kyoto = create_destination(self.japan)

    def order(self, destination=None, **fields):
        return create_order(None, destination or self.kyoto, **fields)


class MonthlyChartTests(ChartTestCase):
    def test_twelve_months_in_order_with_empty_months_at_zero(self):
        self.order(created_at=brussels(2025, 2, 28, 23, 30))  # avant les 12 mois
        self.order(created_at=brussels(2025, 3, 1, 0, 30))  # encore février en UTC, mars à Bruxelles
        self.order(created_at=brussels(2026, 1, 10, 12))
        self.order(created_at=brussels(2026, 1, 31, 23, 30))
        self.order(created_at=brussels(2026, 2, 3, 12))
        self.order(created_at=brussels(2026, 3, 1, 0, 30))  # après la fin de la période

        chart = monthly_chart(custom_period(date(2026, 2, 1), date(2026, 2, 10)))

        labels = [point.label for point in chart.points]
        self.assertEqual(labels[:3], ["mars 2025", "avr. 2025", "mai 2025"])
        self.assertEqual(labels[-3:], ["déc. 2025", "janv. 2026", "févr. 2026"])
        self.assertEqual([point.count for point in chart.points], [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 1])
        self.assertEqual(chart.max_count, 2)
        # Le maximum touche le haut du graphique, un mois vide reste sur l'axe.
        self.assertEqual(chart.points[10].y, chart.top)
        self.assertEqual(chart.points[1].y, chart.bottom)

    def test_departure_basis_counts_by_departure_month(self):
        self.order(created_at=brussels(2026, 1, 5, 12), departure_date=date(2026, 6, 20))
        self.order(created_at=brussels(2026, 6, 5, 12), departure_date=date(2026, 9, 1))

        chart = monthly_chart(custom_period(date(2026, 6, 1), date(2026, 6, 30), DateBasis.DEPARTURE))

        self.assertEqual(chart.points[-1].label, "juin 2026")
        self.assertEqual([point.count for point in chart.points], [0] * 11 + [1])

    def test_no_order_draws_a_flat_line(self):
        chart = monthly_chart(custom_period(date(2026, 2, 1), date(2026, 2, 28)))

        self.assertEqual(chart.max_count, 0)
        self.assertEqual({point.y for point in chart.points}, {chart.bottom})


class CountryChartTests(ChartTestCase):
    @mock.patch("dashboard.services.charts.MAX_COUNTRIES", 2)
    def test_sorted_by_orders_with_the_rest_grouped(self):
        for name, count in (("Pérou", 1), ("Islande", 2), ("Chili", 1)):
            destination = create_destination(create_country(name), name=f"Capitale {name}")
            for _ in range(count):
                self.order(destination, created_at=brussels(2026, 3, 10, 12))
        for _ in range(3):
            # Nom du pays figé à la demande, depuis renommé : la barre porte le nom actuel.
            self.order(created_at=brussels(2026, 3, 10, 12), country_name="Ancien nom")

        chart = country_chart(custom_period(date(2026, 3, 1), date(2026, 3, 31)))

        self.assertEqual(
            [(bar.label, bar.count) for bar in chart.bars], [("Japon", 3), ("Islande", 2), (OTHER_COUNTRIES, 2)]
        )
        self.assertEqual(chart.bars[0].width, BAR_MAX_WIDTH)

    def test_no_order_no_bar(self):
        self.assertEqual(country_chart(custom_period(date(2026, 3, 1), date(2026, 3, 31))).bars, [])


class StatusChartTests(ChartTestCase):
    def setUp(self):
        super().setUp()
        self.march = custom_period(date(2026, 3, 1), date(2026, 3, 31))

    def test_share_of_each_status(self):
        for status in (OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.CONFIRMED):
            self.order(created_at=brussels(2026, 3, 10, 12), status=status)

        chart = status_chart(self.march)

        self.assertEqual(
            [(bar.label, bar.count, bar.percent) for bar in chart.bars],
            [("En attente", 1, f"33{NBSP}%"), ("Confirmée", 2, f"67{NBSP}%"), ("Annulée", 0, f"0{NBSP}%")],
        )
        self.assertEqual([bar.width for bar in chart.bars], [120, 240, 0])

    def test_no_order_gives_zero_percent(self):
        chart = status_chart(self.march)

        self.assertEqual({(bar.percent, bar.width) for bar in chart.bars}, {(f"0{NBSP}%", 0)})


class ChartsPageTests(ChartTestCase):
    def test_svg_charts_with_their_figures(self):
        cache.clear()
        self.order(created_at=brussels(2026, 3, 10, 12))
        self.client.force_login(create_admin())

        response = self.client.get(
            reverse("pilotage_dashboard"),
            {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.ORDERED, "start": "2026-03-01", "end": "2026-03-31"},
        )

        self.assertContains(response, '<svg class="chart-svg"', count=3)
        self.assertContains(response, 'aria-labelledby="chart-monthly-caption"')
        self.assertContains(response, "<summary>Voir les chiffres</summary>", count=3)
        self.assertContains(response, '<tr><th scope="row">mars 2026</th><td>1</td></tr>', html=True)
        self.assertContains(response, '<th scope="row">Japon</th>', html=True)
