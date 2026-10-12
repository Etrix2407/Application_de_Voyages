from decimal import Decimal

from django.test import SimpleTestCase

from common.text import NBSP
from dashboard.services.comparison import BAD, GOOD, NEUTRAL, compare


class CompareTests(SimpleTestCase):
    def test_rise_and_fall_judged_by_the_indicator(self):
        cases = [
            # (actuel, précédent, une hausse est bonne, texte, ton)
            (112, 100, True, f"+12{NBSP}%", GOOD),
            (88, 100, True, f"-12{NBSP}%", BAD),
            (112, 100, False, f"+12{NBSP}%", BAD),  # ex. plus d'annulations
            (88, 100, False, f"-12{NBSP}%", GOOD),
            (Decimal("1500.50"), Decimal("1000.00"), True, f"+50{NBSP}%", GOOD),
            (0.3, 0.2, False, f"+50{NBSP}%", BAD),
            (3000, 2, True, f"+149{NBSP}900{NBSP}%", GOOD),
        ]
        for current, previous, higher_is_better, text, tone in cases:
            with self.subTest(current=current, previous=previous, higher_is_better=higher_is_better):
                comparison = compare(current, previous, higher_is_better)

                self.assertEqual((comparison.text, comparison.tone), (text, tone))

    def test_rounded_to_the_unit(self):
        self.assertEqual(compare(1005, 1000).text, f"+1{NBSP}%")  # 0,5 % arrondi à 1 %
        self.assertEqual(compare(2, 3).text, f"-33{NBSP}%")

    def test_equality_is_neutral(self):
        for current in (100, 1001):  # 1001 : +0,1 %, arrondi à 0 %
            with self.subTest(current=current):
                comparison = compare(current, 1000 if current == 1001 else 100, higher_is_better=False)

                self.assertEqual((comparison.text, comparison.tone, comparison.arrow), (f"0{NBSP}%", NEUTRAL, ""))

    def test_previous_period_at_zero(self):
        self.assertEqual(compare(5, 0).text, "nouveau")
        self.assertEqual(compare(5, 0).tone, GOOD)
        self.assertEqual(compare(5, 0, higher_is_better=False).tone, BAD)
        self.assertFalse(compare(5, 0).is_percentage)
        for zero in (0, Decimal("0.00")):
            with self.subTest(zero=zero):
                self.assertEqual((compare(zero, zero).text, compare(zero, zero).tone), ("—", NEUTRAL))
