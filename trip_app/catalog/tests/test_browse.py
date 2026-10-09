from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from catalog.models import Continent, format_offset
from accounts.tests.factories import create_client

from .factories import (
    TemporaryMediaMixin,
    create_activity,
    create_country,
    create_destination,
    make_image,
)

User = get_user_model()


class FormatOffsetTests(SimpleTestCase):
    def test_formats(self):
        cases = {
            "0": "même heure qu'en Belgique",
            "7": "+7 h",
            "-6": "-6 h",
            "3.5": "+3 h 30",
            "5.75": "+5 h 45",
            "-2.5": "-2 h 30",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_offset(Decimal(value)), expected)


class CountryListTests(TestCase):
    url = reverse("country_list")

    def test_visible_without_login_grouped_by_continent(self):
        create_country("Japon", continent=Continent.ASIA, description="Pays du soleil levant.")
        create_country("Pérou", continent=Continent.AMERICA)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(continent, [p.name for p in countries]) for continent, countries in response.context["continents"]],
            [("Amérique", ["Pérou"]), ("Asie", ["Japon"])],
        )
        self.assertContains(response, "Pays du soleil levant.")
        self.assertContains(response, "Connectez-vous")

    def test_inactive_country_hidden(self):
        create_country("Cuba", active=False)

        self.assertNotContains(self.client.get(self.url), "Cuba")

    def test_description_truncated(self):
        create_country(description=" ".join(["mot"] * 40))

        response = self.client.get(self.url)

        self.assertContains(response, "mot …")


class DetailAccessTests(TestCase):
    def setUp(self):
        self.country = create_country()
        self.destination = create_destination(self.country)
        self.activity = create_activity(self.country)

    def test_details_reserved_to_logged_in_users(self):
        urls = [
            reverse("country_detail", args=[self.country.pk]),
            reverse("destination_detail", args=[self.destination.pk]),
            reverse("activity_detail", args=[self.activity.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

                self.client.force_login(create_client())
                self.assertEqual(self.client.get(url).status_code, 200)
                self.client.logout()
                User.objects.all().delete()


class CountryDetailTests(TemporaryMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(create_client())
        self.country = create_country("Japon", summer_offset=Decimal("7"), winter_offset=Decimal("8"))

    def test_shows_information_and_visible_content(self):
        create_destination(self.country, "Kyoto", photo=make_image())
        create_destination(self.country, "Osaka", active=False)
        create_activity(self.country, "Sumo")
        create_activity(self.country, "Karaoké", active=False)

        response = self.client.get(reverse("country_detail", args=[self.country.pk]))

        self.assertContains(response, "+7 h en été, +8 h en hiver")
        self.assertContains(response, "Kyoto")
        self.assertContains(response, 'alt="Photo : Kyoto"')
        self.assertContains(response, "Sumo")
        self.assertNotContains(response, "Osaka")
        self.assertNotContains(response, "Karaoké")

    def test_inactive_country_not_found(self):
        self.country.active = False
        self.country.save()

        self.assertEqual(self.client.get(reverse("country_detail", args=[self.country.pk])).status_code, 404)


class DestinationDetailTests(TestCase):
    def setUp(self):
        self.client.force_login(create_client())
        self.country = create_country()
        self.destination = create_destination(self.country, "Kyoto")

    def test_shows_only_its_activities(self):
        create_activity(self.country, "Temples", destination=self.destination)
        create_activity(self.country, "Sumo")

        response = self.client.get(reverse("destination_detail", args=[self.destination.pk]))

        self.assertContains(response, "Temples")
        self.assertNotContains(response, "Sumo")

    def test_destination_hidden_if_it_or_its_country_inactive(self):
        url = reverse("destination_detail", args=[self.destination.pk])

        self.country.active = False
        self.country.save()
        self.assertEqual(self.client.get(url).status_code, 404)

        self.country.active = True
        self.country.save()
        self.destination.active = False
        self.destination.save()
        self.assertEqual(self.client.get(url).status_code, 404)


class ActivityDetailTests(TestCase):
    def setUp(self):
        self.client.force_login(create_client())
        self.country = create_country("Japon")

    def test_shows_details(self):
        destination = create_destination(self.country, "Kyoto")
        activity = create_activity(
            self.country, "Temples", destination=destination, duration_minutes=90, minimum_age=12
        )

        response = self.client.get(reverse("activity_detail", args=[activity.pk]))

        self.assertContains(response, "1 h 30")
        self.assertContains(response, "12 ans")
        self.assertContains(response, "Facile")
        self.assertContains(response, reverse("destination_detail", args=[destination.pk]))

    def test_all_ages_without_minimum_age(self):
        activity = create_activity(self.country)

        response = self.client.get(reverse("activity_detail", args=[activity.pk]))

        self.assertContains(response, "Tous âges")

    def test_activity_of_inactive_destination_hidden(self):
        destination = create_destination(self.country, active=False)
        activity = create_activity(self.country, destination=destination)

        response = self.client.get(reverse("activity_detail", args=[activity.pk]))

        self.assertEqual(response.status_code, 404)
