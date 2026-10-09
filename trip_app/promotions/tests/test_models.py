from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin
from catalog.models import Country, Destination
from catalog.tests.factories import create_country, create_destination
from promotions.models import Action, Kind, Promotion, Scope, State, targets_problem
from promotions.services.history import record
from promotions.tests.factories import create_promotion


def errors_of(promotion: Promotion) -> dict:
    try:
        promotion.full_clean()
    except ValidationError as error:
        return error.message_dict
    return {}


class ValidationTests(TestCase):
    def promotion(self, **fields) -> Promotion:
        today = timezone.localdate()
        data = {"name": "Offre", "kind": Kind.PERCENT, "value": Decimal("10"), "starts_on": today, "ends_on": today}
        data.update(fields)
        return Promotion(**data)

    def test_percent_between_1_and_50(self):
        for value, valid in [("0.99", False), ("1", True), ("50", True), ("50.01", False)]:
            with self.subTest(value=value):
                errors = errors_of(self.promotion(value=Decimal(value)))
                self.assertEqual("value" not in errors, valid)

    def test_fixed_amount_above_zero(self):
        self.assertIn("value", errors_of(self.promotion(kind=Kind.FIXED, value=Decimal("0"))))
        self.assertNotIn("value", errors_of(self.promotion(kind=Kind.FIXED, value=Decimal("100"))))

    def test_end_not_before_start(self):
        today = timezone.localdate()

        self.assertIn("ends_on", errors_of(self.promotion(starts_on=today, ends_on=today - timedelta(days=1))))
        self.assertEqual(errors_of(self.promotion(starts_on=today, ends_on=today)), {})

    def test_departure_period_both_dates_in_order(self):
        today = timezone.localdate()

        self.assertIn("departure_until", errors_of(self.promotion(departure_from=today)))
        reversed_period = self.promotion(departure_from=today, departure_until=today - timedelta(days=1))
        self.assertIn("departure_until", errors_of(reversed_period))
        self.assertEqual(errors_of(self.promotion(departure_from=today, departure_until=today)), {})

    def test_code_format(self):
        for code, valid in [("BIENVENUE15", True), ("ABCD", True), ("ABC", False), ("A" * 21, False),
                            ("BIEN VENUE", False), ("ÉTÉ2026", False), ("PROMO-15", False)]:
            with self.subTest(code=code):
                self.assertEqual("code" not in errors_of(self.promotion(code=code)), valid)

    def test_code_stored_in_capitals_and_unique_whatever_the_case(self):
        promotion = create_promotion(code="bienvenue15")
        promotion.refresh_from_db()

        self.assertEqual(promotion.code, "BIENVENUE15")
        self.assertIn("code", errors_of(self.promotion(code="Bienvenue15")))

    def test_several_automatic_promotions_allowed(self):
        create_promotion(code="")
        create_promotion(code="")

        self.assertEqual(Promotion.objects.automatic().count(), 2)

    def test_targets_required_for_country_or_destination_scope(self):
        self.assertIn("countries", targets_problem(Scope.COUNTRIES, [], []))
        self.assertIn("destinations", targets_problem(Scope.DESTINATIONS, [], []))
        self.assertEqual(targets_problem(Scope.CATALOG, [], []), {})


class DiscountLabelTests(TestCase):
    def test_label_in_french_format(self):
        for kind, value, label in [(Kind.PERCENT, "15.00", "-15 %"), (Kind.PERCENT, "12.50", "-12,5 %"),
                                   (Kind.FIXED, "100.00", "-100 €"), (Kind.FIXED, "99.50", "-99,50 €")]:
            with self.subTest(label=label):
                self.assertEqual(Promotion(kind=kind, value=Decimal(value)).discount_label, label)


class StateTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.promotion = create_promotion(starts_on=self.today, ends_on=self.today + timedelta(days=10))

    def test_state_follows_dates_last_day_included(self):
        ends_on = self.promotion.ends_on

        self.assertEqual(self.promotion.state(self.today - timedelta(days=1)), State.UPCOMING)
        self.assertEqual(self.promotion.state(ends_on), State.RUNNING)
        self.assertEqual(self.promotion.state(ends_on + timedelta(days=1)), State.FINISHED)
        self.assertIn(self.promotion, Promotion.objects.running(ends_on))
        self.assertNotIn(self.promotion, Promotion.objects.running(ends_on + timedelta(days=1)))

    def test_disabled_wins_over_dates(self):
        self.promotion.is_active = False
        self.promotion.save()

        self.assertEqual(self.promotion.state(self.today), State.DISABLED)
        self.assertNotIn(self.promotion, Promotion.objects.running(self.today))


class TargetProtectionTests(TestCase):
    def setUp(self):
        self.portugal = create_country("Portugal")
        self.lisbon = create_destination(self.portugal, "Lisbonne")

    def test_targeted_destination_or_country_cannot_be_deleted(self):
        create_promotion(scope=Scope.DESTINATIONS, destinations=[self.lisbon])
        empty_country = create_country("Grèce")
        create_promotion(scope=Scope.COUNTRIES, countries=[empty_country])

        with self.assertRaises(ProtectedError):
            self.lisbon.delete()
        with self.assertRaises(ProtectedError):
            empty_country.delete()

    def test_staff_told_to_deactivate_instead(self):
        create_promotion(scope=Scope.COUNTRIES, countries=[self.portugal])
        self.lisbon.delete()
        self.client.force_login(create_admin())

        response = self.client.post(reverse("manage_delete_country", args=[self.portugal.pk]), follow=True)

        self.assertContains(response, "des promotions")
        self.assertTrue(Country.objects.filter(pk=self.portugal.pk).exists())
        self.assertFalse(Destination.objects.exists())


class HistoryTests(TestCase):
    def test_author_name_kept_after_account_deletion(self):
        admin = create_admin(first_name="Marc", last_name="Dupont")
        promotion = create_promotion()
        record(promotion, Action.CREATED, admin)

        admin.delete()

        self.assertEqual(promotion.created_by_name, "Marc Dupont")
        self.assertIsNone(promotion.history.get().author)
