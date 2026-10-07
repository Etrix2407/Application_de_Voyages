from django.test import TestCase
from django.urls import reverse

from catalog.models import FavoriteActivity, FavoriteDestination
from accounts.tests.factories import PASSWORD, create_agent, create_client

from .factories import create_activity, create_destination, create_country


class FavoriteTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.country = create_country()
        self.destination = create_destination(self.country, "Kyoto")
        self.activity = create_activity(self.country, "Sumo")

    def add_favorite(self, item_type, pk, **data):
        return self.client.post(reverse("add_favorite", args=[item_type, pk]), data)

    def remove_favorite(self, item_type, pk, **data):
        return self.client.post(reverse("remove_favorite", args=[item_type, pk]), data)

    def test_adding_destination_returns_to_its_page(self):
        response = self.add_favorite("destination", self.destination.pk)

        self.assertRedirects(response, reverse("destination_detail", args=[self.destination.pk]))
        self.assertTrue(
            FavoriteDestination.objects.filter(client=self.marie, destination=self.destination).exists()
        )

    def test_adding_twice_creates_no_duplicate(self):
        self.add_favorite("activite", self.activity.pk)
        self.add_favorite("activite", self.activity.pk)

        self.assertEqual(FavoriteActivity.objects.count(), 1)

    def test_hidden_item_cannot_be_added(self):
        self.destination.active = False
        self.destination.save()

        self.assertEqual(self.add_favorite("destination", self.destination.pk).status_code, 404)

    def test_unknown_type(self):
        self.assertEqual(self.add_favorite("country", self.country.pk).status_code, 404)

    def test_get_denied(self):
        url = reverse("add_favorite", args=["activite", self.activity.pk])

        self.assertEqual(self.client.get(url).status_code, 405)

    def test_remove(self):
        self.add_favorite("activite", self.activity.pk)

        response = self.remove_favorite("activite", self.activity.pk)

        self.assertRedirects(response, reverse("favorite_list"))
        self.assertFalse(FavoriteActivity.objects.exists())

    def test_external_or_invalid_redirect_ignored(self):
        detail = reverse("activity_detail", args=[self.activity.pk])
        for next_url in [
            "https://pirate.example.com/",
            "//pirate.example.com/",
            "admin'--",
            "' OR '1'='1",
            "favorite_list",
        ]:
            with self.subTest(next=next_url):
                response = self.add_favorite("activite", self.activity.pk, next=next_url)

                self.assertRedirects(response, detail)

    def test_back_to_original_page(self):
        response = self.remove_favorite("activite", self.activity.pk, next="/catalogue/favoris/")

        self.assertRedirects(response, reverse("favorite_list"))

    def test_button_on_detail_pages(self):
        url = reverse("activity_detail", args=[self.activity.pk])

        self.assertContains(self.client.get(url), "Ajouter à mes favoris")
        self.add_favorite("activite", self.activity.pk)
        self.assertContains(self.client.get(url), "Retirer de mes favoris")

    def test_favorite_list(self):
        self.add_favorite("destination", self.destination.pk)
        self.add_favorite("activite", self.activity.pk)

        response = self.client.get(reverse("favorite_list"))

        self.assertContains(response, reverse("destination_detail", args=[self.destination.pk]))
        self.assertContains(response, reverse("activity_detail", args=[self.activity.pk]))

    def test_inactive_favorite_shown_unavailable(self):
        self.add_favorite("activite", self.activity.pk)
        self.country.active = False
        self.country.save()

        response = self.client.get(reverse("favorite_list"))

        self.assertContains(response, "Sumo")
        self.assertContains(response, "plus disponible")
        self.assertNotContains(response, reverse("activity_detail", args=[self.activity.pk]))
        self.assertContains(response, "Retirer de mes favoris")

    def test_each_client_sees_only_own_favorites(self):
        other = create_client("autre@example.com")
        FavoriteActivity.objects.create(client=other, activity=self.activity)

        response = self.client.get(reverse("favorite_list"))

        self.assertNotContains(response, "Sumo")

    def test_removing_other_client_favorite_has_no_effect(self):
        other = create_client("autre@example.com")
        FavoriteActivity.objects.create(client=other, activity=self.activity)

        self.remove_favorite("activite", self.activity.pk)

        self.assertTrue(FavoriteActivity.objects.filter(client=other).exists())

    def test_favorites_deleted_with_account(self):
        self.add_favorite("activite", self.activity.pk)

        self.client.post(reverse("delete_account"), {"password": PASSWORD})

        self.assertFalse(FavoriteActivity.objects.exists())


class FavoriteAccessTests(TestCase):
    def test_reserved_to_clients(self):
        activity = create_activity(create_country())
        self.client.force_login(create_agent())

        self.assertEqual(self.client.get(reverse("favorite_list")).status_code, 403)
        url = reverse("add_favorite", args=["activite", activity.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertNotContains(
            self.client.get(reverse("activity_detail", args=[activity.pk])), "mes favoris"
        )

    def test_visitor_redirected(self):
        url = reverse("favorite_list")

        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
