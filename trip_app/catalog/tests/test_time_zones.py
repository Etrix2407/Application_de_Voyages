from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.tests.factories import create_agent, create_client
from catalog.models import Country
from catalog.services.time_zones import time_offsets, time_zone_choices, time_zone_label
from catalog.validators import validate_time_zone

from .factories import create_country


class TimeOffsetCalculationTests(SimpleTestCase):
    def offsets(self, zone_name, today=date(2026, 3, 1)):
        result = time_offsets(zone_name, today)
        return result.summer, result.winter, result.today

    def test_country_without_daylight_saving(self):
        # Le Japon ne change pas d'heure : seule l'heure d'été belge fait varier l'écart.
        self.assertEqual(self.offsets("Asia/Tokyo"), (Decimal(7), Decimal(8), Decimal(8)))

    def test_country_changing_hour_like_belgium(self):
        self.assertEqual(self.offsets("America/New_York"), (Decimal(-6), Decimal(-6), Decimal(-6)))

    def test_southern_hemisphere(self):
        # Sydney passe à l'heure d'été quand la Belgique passe à l'heure d'hiver.
        self.assertEqual(self.offsets("Australia/Sydney"), (Decimal(8), Decimal(10), Decimal(10)))

    def test_half_and_quarter_hours(self):
        self.assertEqual(self.offsets("Asia/Kolkata")[:2], (Decimal("3.5"), Decimal("4.5")))
        self.assertEqual(self.offsets("Asia/Kathmandu")[:2], (Decimal("3.75"), Decimal("4.75")))

    def test_today_follows_the_date(self):
        # 9 octobre : Sydney déjà en heure d'été, la Belgique pas encore en heure d'hiver.
        self.assertEqual(time_offsets("Australia/Sydney", date(2026, 10, 9)).today, Decimal(9))

    def test_display(self):
        offsets = time_offsets("Asia/Kolkata", date(2026, 3, 1))

        self.assertEqual(offsets.summer_display, "+3 h 30")
        self.assertEqual(time_offsets("Europe/Brussels", date(2026, 3, 1)).today_display, "même heure qu'en Belgique")


class TimeZoneChoiceTests(SimpleTestCase):
    def test_labels_in_french(self):
        self.assertEqual(time_zone_label("Asia/Tokyo"), "Asie — Tokyo")
        self.assertEqual(time_zone_label("America/Argentina/Buenos_Aires"), "Amérique — Argentina / Buenos Aires")

    def test_only_real_places_offered(self):
        names = [name for name, _ in time_zone_choices()]

        self.assertIn("Asia/Tokyo", names)
        self.assertIn("Pacific/Noumea", names)
        self.assertNotIn("Etc/GMT+3", names)
        self.assertNotIn("UTC", names)

    def test_unknown_time_zone_refused(self):
        for name in ["Etc/GMT+3", "Mars/Olympus", "Asia/Tokio"]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_time_zone(name)


class CountryTimeZoneTests(TestCase):
    def test_country_page_shows_automatic_offsets(self):
        country = create_country("Japon", time_zone="Asia/Tokyo")
        self.client.force_login(create_client())

        response = self.client.get(reverse("country_detail", args=[country.pk]))

        self.assertContains(response, "+7 h en été, +8 h en hiver")
        self.assertContains(response, "(aujourd'hui :")

    def test_country_without_time_zone_waits_for_an_agent(self):
        country = create_country("Pérou", time_zone="")
        self.client.force_login(create_agent())

        response = self.client.get(reverse("manage_country", args=[country.pk]))

        self.assertContains(response, "Fuseau horaire à renseigner")

    def test_form_requires_a_time_zone_from_the_list(self):
        self.client.force_login(create_agent())
        data = {
            "name": "Pérou",
            "continent": "america",
            "main_language": "espagnol",
            "currency": "sol",
            "description": "Andes.",
            "visa": "not_required",
            "active": "on",
        }

        for time_zone in ["", "Etc/GMT+5"]:
            with self.subTest(time_zone=time_zone):
                response = self.client.post(reverse("manage_create_country"), {**data, "time_zone": time_zone})

                self.assertEqual(response.status_code, 200)
                self.assertFalse(Country.objects.exists())

        self.client.post(reverse("manage_create_country"), {**data, "time_zone": "America/Lima"})

        self.assertEqual(Country.objects.get().time_zone, "America/Lima")
