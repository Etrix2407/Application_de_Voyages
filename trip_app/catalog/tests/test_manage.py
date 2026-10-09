from django.test import TestCase
from django.urls import reverse

from catalog.models import Activity, Destination, Country
from accounts.tests.factories import create_admin, create_agent, create_client

from .factories import (
    TemporaryMediaMixin,
    create_activity,
    create_country,
    create_destination,
    make_image,
)


def country_data(**fields):
    data = {
        "name": "Pérou",
        "continent": "america",
        "main_language": "espagnol",
        "currency": "sol",
        "description": "Description.",
        "visa": "not_required",
        "summer_offset": "-7",
        "winter_offset": "-6",
        "active": "on",
    }
    data.update(fields)
    return data


def activity_data(**fields):
    data = {
        "name": "Randonnée",
        "description": "Description.",
        "category": "sport",
        "duration_minutes": "240",
        "price_per_person": "60.00",
        "difficulty": "hard",
        "minimum_age": "",
        "destination": "",
        "active": "on",
    }
    data.update(fields)
    return data


class ManageAccessTests(TestCase):
    def setUp(self):
        self.country = create_country()
        self.destination = create_destination(self.country)
        self.activity = create_activity(self.country)

    def urls(self):
        return [
            reverse("manage_country_list"),
            reverse("manage_create_country"),
            reverse("manage_country", args=[self.country.pk]),
            reverse("manage_edit_country", args=[self.country.pk]),
            reverse("manage_delete_country", args=[self.country.pk]),
            reverse("manage_create_destination", args=[self.country.pk]),
            reverse("manage_edit_destination", args=[self.destination.pk]),
            reverse("manage_delete_destination", args=[self.destination.pk]),
            reverse("manage_create_activity", args=[self.country.pk]),
            reverse("manage_edit_activity", args=[self.activity.pk]),
            reverse("manage_delete_activity", args=[self.activity.pk]),
        ]

    def test_client_denied(self):
        self.client.force_login(create_client())

        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Country.objects.exists())

    def test_visitor_redirected(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_agent_and_administrator_allowed(self):
        for user in [create_agent(), create_admin()]:
            self.client.force_login(user)
            with self.subTest(role=user.role):
                self.assertEqual(self.client.get(reverse("manage_country_list")).status_code, 200)


class ManageCountryTests(TemporaryMediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(create_agent())

    def test_list_includes_inactive_countries(self):
        create_country("Japon")
        create_country("Cuba", active=False)

        response = self.client.get(reverse("manage_country_list"))

        self.assertContains(response, "Japon")
        self.assertContains(response, "Cuba")
        self.assertContains(response, "Désactivé")

    def test_create_country(self):
        response = self.client.post(reverse("manage_create_country"), country_data())

        country = Country.objects.get(name="Pérou")
        self.assertRedirects(response, reverse("manage_country", args=[country.pk]))
        self.assertTrue(country.active)

    def test_duplicate_name_rejected(self):
        create_country("Pérou")

        response = self.client.post(reverse("manage_create_country"), country_data(name="PÉROU"))

        self.assertContains(response, "Un pays avec ce nom existe déjà.")

    def test_deactivate_country(self):
        country = create_country("Pérou")

        data = country_data()
        del data["active"]
        self.client.post(reverse("manage_edit_country", args=[country.pk]), data)

        country.refresh_from_db()
        self.assertFalse(country.active)

    def test_delete_empty_country(self):
        country = create_country()
        url = reverse("manage_delete_country", args=[country.pk])

        self.assertContains(self.client.get(url), "définitive")
        self.assertRedirects(self.client.post(url), reverse("manage_country_list"))
        self.assertFalse(Country.objects.exists())

    def test_country_with_content_cannot_be_deleted(self):
        country = create_country()
        create_destination(country)

        response = self.client.post(reverse("manage_delete_country", args=[country.pk]), follow=True)

        self.assertContains(response, "ne peut pas être supprimé")
        self.assertTrue(Country.objects.filter(pk=country.pk).exists())

    def test_page_shows_destinations_and_activities(self):
        country = create_country()
        create_destination(country, "Kyoto", photo=make_image())
        create_activity(country, "Sumo")

        response = self.client.get(reverse("manage_country", args=[country.pk]))

        self.assertContains(response, "Kyoto")
        self.assertContains(response, 'alt="Photo : Kyoto"')
        self.assertContains(response, "Sumo")


class ManageDestinationTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.country = create_country()

    def test_create_destination_in_country(self):
        response = self.client.post(
            reverse("manage_create_destination", args=[self.country.pk]),
            {
                "name": "Kyoto",
                "description": "Temples.",
                "start_month": "11",
                "end_month": "3",
                "price_from": "1200",
                "photo": "",
                "active": "on",
            },
        )

        self.assertRedirects(response, reverse("manage_country", args=[self.country.pk]))
        destination = Destination.objects.get()
        self.assertEqual(destination.country, self.country)
        self.assertEqual(destination.ideal_months(), [11, 12, 1, 2, 3])

    def test_country_not_editable(self):
        destination = create_destination(self.country)
        other = create_country("Pérou")

        self.client.post(
            reverse("manage_edit_destination", args=[destination.pk]),
            {"name": "Kyoto", "description": "x", "country": other.pk, "active": "on"},
        )

        destination.refresh_from_db()
        self.assertEqual(destination.country, self.country)

    def test_delete_keeps_activities(self):
        destination = create_destination(self.country)
        activity = create_activity(self.country, destination=destination)
        url = reverse("manage_delete_destination", args=[destination.pk])

        self.assertContains(self.client.get(url), "restent dans le pays")
        self.client.post(url)

        activity.refresh_from_db()
        self.assertIsNone(activity.destination)


class ManageActivityTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.country = create_country()

    def test_create_activity_without_destination(self):
        response = self.client.post(
            reverse("manage_create_activity", args=[self.country.pk]), activity_data()
        )

        self.assertRedirects(response, reverse("manage_country", args=[self.country.pk]))
        activity = Activity.objects.get()
        self.assertEqual(activity.country, self.country)
        self.assertIsNone(activity.destination)
        self.assertIsNone(activity.minimum_age)

    def test_destination_choices_limited_to_country(self):
        kyoto = create_destination(self.country, "Kyoto")
        cusco = create_destination(create_country("Pérou"), "Cusco")

        response = self.client.get(reverse("manage_create_activity", args=[self.country.pk]))

        choices = list(response.context["form"].fields["destination"].queryset)
        self.assertEqual(choices, [kyoto])
        self.assertNotIn(cusco, choices)

    def test_destination_from_other_country_rejected(self):
        cusco = create_destination(create_country("Pérou"), "Cusco")

        response = self.client.post(
            reverse("manage_create_activity", args=[self.country.pk]),
            activity_data(destination=cusco.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Activity.objects.exists())

    def test_edit_then_delete(self):
        activity = create_activity(self.country)

        self.client.post(
            reverse("manage_edit_activity", args=[activity.pk]),
            activity_data(name="Sumo", minimum_age="12"),
        )
        activity.refresh_from_db()
        self.assertEqual(activity.name, "Sumo")
        self.assertEqual(activity.minimum_age, 12)

        self.client.post(reverse("manage_delete_activity", args=[activity.pk]))
        self.assertFalse(Activity.objects.exists())
