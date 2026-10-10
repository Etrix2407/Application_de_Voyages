from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_agent
from catalog.tests.factories import create_country
from promotions.models import Action, Promotion, Scope, State
from promotions.tests.factories import create_promotion


def form_data(**fields) -> dict:
    today = timezone.localdate()
    data = {
        "name": "Semaine du Portugal",
        "description": "",
        "kind": "percent",
        "value": "15",
        "scope": "catalog",
        "base": "total",
        "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=30)).isoformat(),
        "code": "",
    }
    data.update(fields)
    return data


class CreatePromotionTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin(first_name="Marc", last_name="Dupont"))
        self.portugal = create_country("Portugal")
        self.url = reverse("manage_create_promotion")

    def test_created_with_history(self):
        response = self.client.post(self.url, form_data(code="bienvenue15"), follow=True)

        promotion = Promotion.objects.get()
        self.assertContains(response, "a été créée")
        self.assertEqual(promotion.code, "BIENVENUE15")
        self.assertEqual(promotion.created_by_name, "Marc Dupont")
        self.assertContains(response, "<dt>Créée par</dt><dd>Marc Dupont</dd>", html=True)

    def test_country_scope_needs_a_country(self):
        response = self.client.post(self.url, form_data(scope="countries"))

        self.assertContains(response, "Choisissez au moins un pays.")
        self.assertFalse(Promotion.objects.exists())

    def test_only_targets_of_the_chosen_scope_are_kept(self):
        self.client.post(self.url, form_data(scope="catalog", countries=[self.portugal.pk]))

        self.assertFalse(Promotion.objects.get().countries.exists())

    def test_end_date_cannot_be_in_the_past(self):
        yesterday = timezone.localdate() - timedelta(days=1)

        response = self.client.post(
            self.url, form_data(starts_on=(yesterday - timedelta(days=5)).isoformat(), ends_on=yesterday.isoformat())
        )

        self.assertContains(response, "ne peut pas être dans le passé")


class EditPromotionTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin())
        self.today = timezone.localdate()

    def test_changes_noted_in_history(self):
        promotion = create_promotion()
        data = form_data(name="Semaine du Portugal prolongée", ends_on=(self.today + timedelta(days=60)).isoformat())

        self.client.post(reverse("manage_edit_promotion", args=[promotion.pk]), data)

        change = promotion.history.get()
        self.assertEqual(change.action, Action.UPDATED)
        self.assertIn("nom", change.details)
        self.assertIn("date de fin", change.details)

    def test_end_date_can_be_brought_forward_but_not_into_the_past(self):
        promotion = create_promotion()
        url = reverse("manage_edit_promotion", args=[promotion.pk])

        self.client.post(url, form_data(ends_on=self.today.isoformat()))
        response = self.client.post(url, form_data(ends_on=(self.today - timedelta(days=1)).isoformat()))

        promotion.refresh_from_db()
        self.assertEqual(promotion.ends_on, self.today)
        self.assertContains(response, "ne peut pas être dans le passé")

    def test_finished_promotion_can_still_be_renamed(self):
        start, end = self.today - timedelta(days=20), self.today - timedelta(days=10)
        promotion = create_promotion(starts_on=start, ends_on=end)
        data = form_data(name="Ancienne offre", starts_on=start.isoformat(), ends_on=end.isoformat())

        self.client.post(reverse("manage_edit_promotion", args=[promotion.pk]), data)

        promotion.refresh_from_db()
        self.assertEqual(promotion.name, "Ancienne offre")


class DisableAndDeleteTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin())
        self.promotion = create_promotion()

    def test_disable_once_with_history(self):
        url = reverse("manage_disable_promotion", args=[self.promotion.pk])

        self.client.post(url)
        response = self.client.post(url, follow=True)

        self.promotion.refresh_from_db()
        self.assertEqual(self.promotion.state(), State.DISABLED)
        self.assertEqual(self.promotion.history.get().action, Action.DISABLED)
        self.assertContains(response, "déjà désactivée")

    def test_unused_promotion_deleted(self):
        response = self.client.post(reverse("manage_delete_promotion", args=[self.promotion.pk]), follow=True)

        self.assertContains(response, "a été supprimée")
        self.assertFalse(Promotion.objects.exists())


class AgentConsultationTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        portugal = create_country("Portugal")
        self.promotion = create_promotion(code="BIENVENUE15", scope=Scope.COUNTRIES, countries=[portugal])

    def test_list_shows_promotions_without_admin_actions(self):
        response = self.client.get(reverse("manage_promotions"))

        self.assertContains(response, "Semaine du Portugal")
        self.assertContains(response, "-10 %")
        self.assertContains(response, "BIENVENUE15")
        self.assertContains(response, "En cours")
        self.assertNotContains(response, reverse("manage_create_promotion"))

    def test_detail_without_admin_actions(self):
        response = self.client.get(reverse("manage_promotion_detail", args=[self.promotion.pk]))

        self.assertContains(response, "Portugal")
        self.assertNotContains(response, reverse("manage_edit_promotion", args=[self.promotion.pk]))
        self.assertNotContains(response, reverse("manage_disable_promotion", args=[self.promotion.pk]))
