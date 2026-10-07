from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import SimpleTestCase, TestCase

from catalog.models import Activity, Category, Continent, Destination, Difficulty, Month, Country
from catalog.validators import validate_time_offset

from .factories import create_activity, create_destination, create_country


class CountryTests(TestCase):
    def test_name_unique_case_insensitive(self):
        create_country("Pérou")
        duplicate = Country(
            name=" PÉROU ",
            continent=Continent.ASIA,
            main_language="japonais",
            currency="yen",
            description="x",
            summer_offset=0,
            winter_offset=0,
        )

        with self.assertRaises(ValidationError) as error:
            duplicate.full_clean()
        self.assertIn("Un pays avec ce nom existe déjà.", str(error.exception))

    def test_same_name_without_accents_rejected(self):
        create_country("Pérou")

        with self.assertRaises(ValidationError):
            Country(
                name="Perou",
                continent=Continent.AMERICA,
                main_language="espagnol",
                currency="sol",
                description="x",
                summer_offset=0,
                winter_offset=0,
            ).full_clean()

    def test_empty_country_can_be_deleted(self):
        country = create_country()

        self.assertTrue(country.can_be_deleted())
        country.delete()
        self.assertFalse(Country.objects.exists())

    def test_country_with_destination_cannot_be_deleted(self):
        country = create_country()
        create_destination(country)

        self.assertFalse(country.can_be_deleted())
        with self.assertRaises(ProtectedError):
            country.delete()

    def test_country_with_activity_cannot_be_deleted(self):
        country = create_country()
        create_activity(country)

        self.assertFalse(country.can_be_deleted())
        with self.assertRaises(ProtectedError):
            country.delete()


class TimeOffsetTests(SimpleTestCase):
    def test_valid_values(self):
        for value in ["-12", "0", "5.5", "5.75", "14"]:
            with self.subTest(value=value):
                validate_time_offset(Decimal(value))

    def test_invalid_values(self):
        for value in ["-12.25", "14.5", "5.1", "3.33"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_time_offset(Decimal(value))


class IdealPeriodTests(SimpleTestCase):
    def period(self, start, end):
        return Destination(start_month=start, end_month=end)

    def test_simple_period(self):
        destination = self.period(Month.APRIL, Month.JUNE)

        self.assertEqual(destination.ideal_months(), [4, 5, 6])
        self.assertEqual(destination.ideal_period(), "d'avril à juin")

    def test_period_spanning_new_year(self):
        destination = self.period(Month.NOVEMBER, Month.MARCH)

        self.assertEqual(destination.ideal_months(), [11, 12, 1, 2, 3])
        self.assertEqual(destination.ideal_period(), "de novembre à mars")

    def test_single_month(self):
        destination = self.period(Month.AUGUST, Month.AUGUST)

        self.assertEqual(destination.ideal_months(), [8])
        self.assertEqual(destination.ideal_period(), "août")

    def test_all_year(self):
        self.assertEqual(self.period(Month.JANUARY, Month.DECEMBER).ideal_period(), "toute l'année")

    def test_without_period(self):
        self.assertEqual(self.period(None, None).ideal_months(), [])
        self.assertEqual(self.period(None, None).ideal_period(), "")


class DestinationTests(TestCase):
    def test_optional_fields(self):
        destination = Destination(country=create_country(), name="Kyoto", description="x")

        destination.full_clean()

    def test_incomplete_period_rejected(self):
        destination = Destination(
            country=create_country(), name="Kyoto", description="x", start_month=Month.APRIL
        )

        with self.assertRaises(ValidationError):
            destination.full_clean()

    def test_deletion_keeps_activities_in_country(self):
        country = create_country()
        destination = create_destination(country)
        activity = create_activity(country, destination=destination)

        destination.delete()

        activity.refresh_from_db()
        self.assertIsNone(activity.destination)
        self.assertEqual(activity.country, country)


class ActivityTests(TestCase):
    def test_destination_from_other_country_rejected(self):
        japan = create_country("Japon")
        peru = create_country("Pérou")
        activity = Activity(
            country=japan,
            destination=create_destination(peru, "Cusco"),
            name="Randonnée",
            description="x",
            category=Category.SPORT,
            duration_minutes=120,
            price_per_person=Decimal("30"),
            difficulty=Difficulty.MEDIUM,
        )

        with self.assertRaises(ValidationError) as error:
            activity.full_clean()
        self.assertIn("destination", error.exception.message_dict)

    def test_duration_display(self):
        cases = {45: "45 min", 60: "1 h", 90: "1 h 30", 125: "2 h 05"}
        for minutes, expected in cases.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(Activity(duration_minutes=minutes).duration_display(), expected)


class VisibilityTests(TestCase):
    def setUp(self):
        self.country = create_country()
        self.destination = create_destination(self.country)
        self.activity_without_destination = create_activity(self.country, "Sumo")
        self.activity_with_destination = create_activity(
            self.country, "Temples", destination=self.destination
        )

    def test_all_visible_when_all_active(self):
        self.assertEqual(Country.objects.visible().count(), 1)
        self.assertEqual(Destination.objects.visible().count(), 1)
        self.assertEqual(Activity.objects.visible().count(), 2)

    def test_inactive_country_hides_all_its_content(self):
        self.country.active = False
        self.country.save()

        self.assertFalse(Country.objects.visible().exists())
        self.assertFalse(Destination.objects.visible().exists())
        self.assertFalse(Activity.objects.visible().exists())

    def test_inactive_destination_hides_its_activities(self):
        self.destination.active = False
        self.destination.save()

        self.assertFalse(Destination.objects.visible().exists())
        self.assertEqual(list(Activity.objects.visible()), [self.activity_without_destination])

    def test_inactive_activity_hidden(self):
        self.activity_without_destination.active = False
        self.activity_without_destination.save()

        self.assertEqual(list(Activity.objects.visible()), [self.activity_with_destination])
