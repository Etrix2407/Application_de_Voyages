from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from catalog.tests.factories import create_country, create_destination
from promotions.models import Base, Kind, Promotion, Scope
from promotions.services.discounts import Offer, PriceParts, best_offer, covers, discount_amount, offer_for
from promotions.tests.factories import create_promotion

# Lisbonne à 800 € + une activité à 60 € (exemple du Recap 4).
LISBON_TRIP = PriceParts(stay=Decimal("800"), activities=Decimal("60"))


def promotion(kind=Kind.PERCENT, value="10", base=Base.TOTAL) -> Promotion:
    return Promotion(kind=kind, value=Decimal(value), base=base)


class DiscountAmountTests(TestCase):
    def test_percent_applies_to_its_base_only(self):
        self.assertEqual(discount_amount(promotion(base=Base.STAY), LISBON_TRIP), Decimal("80.00"))
        self.assertEqual(discount_amount(promotion(base=Base.ACTIVITIES), LISBON_TRIP), Decimal("6.00"))
        self.assertEqual(discount_amount(promotion(base=Base.TOTAL), LISBON_TRIP), Decimal("86.00"))

    def test_percent_rounded_to_the_cent(self):
        prices = PriceParts(stay=Decimal("33.33"), activities=Decimal("0"))

        self.assertEqual(discount_amount(promotion(value="15"), prices), Decimal("5.00"))

    def test_fixed_amount_once_per_order(self):
        self.assertEqual(discount_amount(promotion(Kind.FIXED, "100"), LISBON_TRIP), Decimal("100.00"))

    def test_fixed_amount_capped_at_its_base(self):
        capped = promotion(Kind.FIXED, "100", Base.ACTIVITIES)

        self.assertEqual(discount_amount(capped, LISBON_TRIP), Decimal("60.00"))

    def test_no_discount_means_not_applicable(self):
        no_activity = PriceParts(stay=Decimal("800"), activities=Decimal("0"))

        self.assertIsNone(offer_for(promotion(base=Base.ACTIVITIES), no_activity))


class BestOfferTests(TestCase):
    def test_biggest_discount_in_euros_wins(self):
        small, big = create_promotion(name="Petite"), create_promotion(name="Grande")

        best = best_offer([Offer(big, Decimal("150")), Offer(small, Decimal("100")), None])

        self.assertEqual(best.promotion, big)

    def test_tie_goes_to_most_recently_created(self):
        older = create_promotion(name="Ancienne", created_at=timezone.now() - timedelta(days=1))
        newer = create_promotion(name="Récente")

        best = best_offer([Offer(newer, Decimal("100")), Offer(older, Decimal("100"))])

        self.assertEqual(best.promotion, newer)

    def test_no_offer(self):
        self.assertIsNone(best_offer([None]))


class CoversTests(TestCase):
    def setUp(self):
        self.portugal = create_country("Portugal")
        self.lisbon = create_destination(self.portugal, "Lisbonne")
        self.porto = create_destination(self.portugal, "Porto")
        self.kyoto = create_destination(create_country("Japon"), "Kyoto")
        self.departure = timezone.localdate() + timedelta(days=60)

    def test_scope(self):
        whole_catalog = create_promotion()
        portugal = create_promotion(scope=Scope.COUNTRIES, countries=[self.portugal])
        lisbon = create_promotion(scope=Scope.DESTINATIONS, destinations=[self.lisbon])

        self.assertTrue(covers(whole_catalog, self.kyoto, self.departure))
        self.assertTrue(covers(portugal, self.porto, self.departure))
        self.assertFalse(covers(portugal, self.kyoto, self.departure))
        self.assertTrue(covers(lisbon, self.lisbon, self.departure))
        self.assertFalse(covers(lisbon, self.porto, self.departure))

    def test_departure_period_bounds_included(self):
        period = create_promotion(departure_from=self.departure, departure_until=self.departure + timedelta(days=30))

        self.assertTrue(covers(period, self.lisbon, self.departure))
        self.assertTrue(covers(period, self.lisbon, self.departure + timedelta(days=30)))
        self.assertFalse(covers(period, self.lisbon, self.departure - timedelta(days=1)))
        self.assertFalse(covers(period, self.lisbon, self.departure + timedelta(days=31)))
