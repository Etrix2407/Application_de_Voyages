from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from catalog.models import Category, Continent, Difficulty, Month
from catalog.services.search import Criteria, search
from accounts.tests.factories import create_client
from common.text import normalize

from .factories import create_activity, create_destination, create_country


def names(items):
    return sorted(item.name for item in items)


class NormalizeTests(SimpleTestCase):
    def test_ignores_accents_and_case(self):
        self.assertEqual(normalize("PÉROU Île Çà"), "perou ile ca")


class SearchTests(TestCase):
    def setUp(self):
        self.japan = create_country("Japon", continent=Continent.ASIA, description="Temples et sushis.")
        self.peru = create_country("Pérou", continent=Continent.AMERICA, description="Andes.")
        self.kyoto = create_destination(
            self.japan,
            "Kyoto",
            description="Ancienne capitale, temples.",
            start_month=Month.NOVEMBER,
            end_month=Month.MARCH,
            price_from=Decimal("1500"),
        )
        self.cusco = create_destination(
            self.peru, "Cusco", description="Porte du Machu Picchu.", start_month=Month.MAY, end_month=Month.SEPTEMBER
        )
        self.the = create_activity(
            self.japan,
            "Cérémonie du thé",
            description="Tradition japonaise.",
            category=Category.CULTURE,
            price_per_person=Decimal("45"),
            difficulty=Difficulty.EASY,
            destination=self.kyoto,
        )
        self.trek = create_activity(
            self.peru,
            "Trek de l'Inca",
            description="Randonnée vers le Machu Picchu.",
            category=Category.ADVENTURE,
            price_per_person=Decimal("600"),
            difficulty=Difficulty.HARD,
            minimum_age=16,
        )

    def test_keyword_without_accent_or_case(self):
        results = search(Criteria(keyword="perou"))

        self.assertEqual(names(results.countries), ["Pérou"])

    def test_keyword_in_name_or_description(self):
        results = search(Criteria(keyword="temples"))

        self.assertEqual(names(results.countries), ["Japon"])
        self.assertEqual(names(results.destinations), ["Kyoto"])
        self.assertEqual(results.activities, [])

    def test_several_words_all_required(self):
        results = search(Criteria(keyword="machu randonnee"))

        self.assertEqual(names(results.activities), ["Trek de l'Inca"])
        self.assertEqual(results.destinations, [])

    def test_continent(self):
        results = search(Criteria(continent=Continent.AMERICA))

        self.assertEqual(names(results.countries), ["Pérou"])
        self.assertEqual(names(results.destinations), ["Cusco"])
        self.assertEqual(names(results.activities), ["Trek de l'Inca"])

    def test_category_shows_only_activities(self):
        results = search(Criteria(category=Category.CULTURE))

        self.assertEqual(names(results.activities), ["Cérémonie du thé"])
        self.assertEqual(results.countries, [])
        self.assertEqual(results.destinations, [])

    def test_difficulty(self):
        results = search(Criteria(difficulty=Difficulty.HARD))

        self.assertEqual(names(results.activities), ["Trek de l'Inca"])

    def test_budget_applies_to_activities_and_destinations(self):
        results = search(Criteria(max_budget=Decimal("100")))

        self.assertEqual(names(results.activities), ["Cérémonie du thé"])
        # Kyoto (1500 €) est écartée ; Cusco (sans prix) est gardée.
        self.assertEqual(names(results.destinations), ["Cusco"])
        self.assertEqual(results.countries, [])

    def test_budget_includes_exact_price(self):
        results = search(Criteria(max_budget=Decimal("1500")))

        self.assertIn("Kyoto", names(results.destinations))

    def test_month_shows_only_destinations(self):
        results = search(Criteria(month=Month.JANUARY))

        self.assertEqual(names(results.destinations), ["Kyoto"])
        self.assertEqual(results.activities, [])

    def test_month_excludes_destinations_without_period(self):
        create_destination(self.japan, "Osaka")

        results = search(Criteria(month=Month.JANUARY))

        self.assertNotIn("Osaka", names(results.destinations))

    def test_traveller_age(self):
        self.assertEqual(names(search(Criteria(age=10)).activities), ["Cérémonie du thé"])
        self.assertEqual(
            names(search(Criteria(age=16)).activities), ["Cérémonie du thé", "Trek de l'Inca"]
        )

    def test_combined_filters(self):
        results = search(
            Criteria(keyword="the", continent=Continent.ASIA, max_budget=Decimal("50"))
        )

        self.assertEqual(names(results.activities), ["Cérémonie du thé"])

    def test_inactive_items_excluded(self):
        self.peru.active = False
        self.peru.save()

        results = search(Criteria(keyword="machu"))

        self.assertEqual(results.total(), 0)


class SearchPageTests(TestCase):
    url = reverse("search")

    def setUp(self):
        self.client.force_login(create_client())
        create_activity(create_country("Japon"), "Cérémonie du thé", category=Category.CULTURE)

    def test_empty_form_without_results(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["results"])

    def test_results_displayed(self):
        response = self.client.get(self.url, {"keyword": "CEREMONIE"})

        self.assertContains(response, "1 résultat")
        self.assertContains(response, "Cérémonie du thé")

    def test_no_results(self):
        response = self.client.get(self.url, {"keyword": "volcan"})

        self.assertContains(response, "Aucun résultat")

    def test_invalid_values(self):
        response = self.client.get(self.url, {"max_budget": "-5", "age": "abc"})

        self.assertIsNone(response.context["results"])
        self.assertTrue(response.context["form"].errors)
