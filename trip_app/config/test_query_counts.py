"""Pages de liste : le nombre de requêtes SQL ne dépend pas du nombre de lignes affichées.

Une requête de plus par ligne (problème « N+1 ») passerait inaperçue avec quelques
données de test, mais ralentirait fortement les pages avec 1 000 clients. Chaque test
affiche la page avec une ligne, puis avec plusieurs, et compare le nombre de requêtes.
"""

from itertools import count

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.models import FavoriteActivity, FavoriteDestination
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import Status
from orders.tests.factories import create_order
from promotions.models import Scope
from promotions.tests.factories import create_promotion
from reviews.models import ReviewStatus
from reviews.tests.factories import create_review, create_trip_done

EXTRA_ROWS = 4


class QueryCountTests(TestCase):
    def setUp(self):
        self.numbers = count(1)
        self.country = create_country()
        self.marie = create_client()

    def unique(self, prefix: str) -> str:
        return f"{prefix} {next(self.numbers)}"

    def assert_constant_queries(self, url: str, add_row):
        """`add_row()` ajoute une ligne à la page ; la page doit coûter autant de requêtes avec 1 ou 5 lignes."""
        add_row()
        with CaptureQueriesContext(connection) as with_one_row:
            self.assertEqual(self.client.get(url).status_code, 200)
        for _ in range(EXTRA_ROWS):
            add_row()
        with CaptureQueriesContext(connection) as with_more_rows:
            self.client.get(url)

        self.assertEqual(
            len(with_more_rows), len(with_one_row),
            "Une requête SQL est faite pour chaque ligne affichée (problème N+1).",
        )

    # --- Pages du client ---

    def test_my_orders(self):
        self.client.force_login(self.marie)
        destination = create_destination(self.country)

        def add_order():
            create_order(self.marie, destination, [create_activity(self.country, self.unique("Visite"))])

        self.assert_constant_queries(reverse("my_orders"), add_order)

    def test_favorites(self):
        self.client.force_login(self.marie)

        def add_favorites():
            destination = create_destination(self.country, self.unique("Ville"))
            FavoriteDestination.objects.create(client=self.marie, destination=destination)
            activity = create_activity(self.country, self.unique("Visite"), destination=destination)
            FavoriteActivity.objects.create(client=self.marie, activity=activity)

        self.assert_constant_queries(reverse("favorite_list"), add_favorites)

    def test_country_detail(self):
        self.client.force_login(self.marie)

        def add_content():
            destination = create_destination(self.country, self.unique("Ville"))
            create_activity(self.country, self.unique("Visite"), destination=destination)

        self.assert_constant_queries(reverse("country_detail", args=[self.country.pk]), add_content)

    def test_search(self):
        self.client.force_login(self.marie)

        def add_matches():
            destination = create_destination(self.country, self.unique("Temple"))
            create_activity(self.country, self.unique("Temple visite"), destination=destination)

        self.assert_constant_queries(reverse("search") + "?keyword=temple", add_matches)

    # --- Pages du personnel ---

    def add_order_of_new_client(self):
        client = create_client(email=f"{self.unique('client').replace(' ', '')}@example.com", last_name="Dupont")
        create_order(client, create_destination(self.country, self.unique("Ville")))

    def test_staff_order_list(self):
        self.client.force_login(create_agent())

        self.assert_constant_queries(reverse("manage_orders"), self.add_order_of_new_client)

    def test_staff_order_list_filtered_by_client(self):
        self.client.force_login(create_agent())

        self.assert_constant_queries(reverse("manage_orders") + "?client=dupont", self.add_order_of_new_client)

    def test_client_list(self):
        self.client.force_login(create_agent())

        def add_client():
            create_client(email=f"{self.unique('client').replace(' ', '')}@example.com")

        self.assert_constant_queries(reverse("client_list"), add_client)

    def test_staff_list(self):
        self.client.force_login(create_admin())

        def add_agent():
            create_agent(email=f"{self.unique('agent').replace(' ', '')}@example.com")

        self.assert_constant_queries(reverse("staff_list"), add_agent)

    def test_promotion_list(self):
        self.client.force_login(create_agent())

        def add_promotion():
            destination = create_destination(self.country, self.unique("Ville"))
            create_promotion(scope=Scope.DESTINATIONS, destinations=[destination])
            create_promotion(scope=Scope.COUNTRIES, countries=[self.country])

        self.assert_constant_queries(reverse("manage_promotions"), add_promotion)

    def test_promotion_statistics(self):
        self.client.force_login(create_agent())
        promotion = create_promotion()

        def add_orders():
            client = create_client(email=f"{self.unique('client').replace(' ', '')}@example.com")
            destination = create_destination(self.country, self.unique("Ville"))
            create_order(client, destination, promotion=promotion)
            create_order(client, destination, promotion=promotion, status=Status.CANCELLED)

        self.assert_constant_queries(reverse("manage_promotion_statistics", args=[promotion.pk]), add_orders)

    def test_manage_country_page(self):
        self.client.force_login(create_agent())

        def add_content():
            destination = create_destination(self.country, self.unique("Ville"))
            create_activity(self.country, self.unique("Visite"), destination=destination)

        self.assert_constant_queries(reverse("manage_country", args=[self.country.pk]), add_content)

    # --- Avis (v3) ---

    def add_published_review(self, destination):
        traveller = create_client(email=f"{self.unique('voyageur').replace(' ', '')}@example.com")
        create_review(create_trip_done(traveller, destination), status=ReviewStatus.PUBLISHED)

    def test_destination_list_with_ratings(self):
        def add_rated_destination():
            self.add_published_review(create_destination(self.country, self.unique("Ville")))

        self.assert_constant_queries(reverse("destination_list"), add_rated_destination)

    def test_destination_page_with_reviews(self):
        destination = create_destination(self.country, "Kyoto")

        self.assert_constant_queries(
            reverse("destination_detail", args=[destination.pk]), lambda: self.add_published_review(destination)
        )

    def test_moderation_queue(self):
        self.client.force_login(create_agent())
        destination = create_destination(self.country, "Kyoto")

        def add_pending_review():
            traveller = create_client(email=f"{self.unique('voyageur').replace(' ', '')}@example.com")
            create_review(create_trip_done(traveller, destination))

        self.assert_constant_queries(reverse("manage_pending_reviews"), add_pending_review)

    def test_staff_review_list(self):
        self.client.force_login(create_agent())
        destination = create_destination(self.country, "Kyoto")

        self.assert_constant_queries(reverse("manage_reviews"), lambda: self.add_published_review(destination))

    # --- Promotions visibles par le public (v4) ---

    def test_destination_list_with_promo_labels(self):
        create_promotion(scope=Scope.COUNTRIES, countries=[self.country])

        def add_promoted_destination():
            destination = create_destination(self.country, self.unique("Ville"))
            create_promotion(scope=Scope.DESTINATIONS, destinations=[destination])

        self.assert_constant_queries(reverse("destination_list"), add_promoted_destination)

    def test_public_offers(self):
        def add_offer():
            destination = create_destination(self.country, self.unique("Ville"))
            create_promotion(scope=Scope.DESTINATIONS, destinations=[destination])
            create_promotion(scope=Scope.COUNTRIES, countries=[self.country])

        self.assert_constant_queries(reverse("offers"), add_offer)

    def test_home_with_top_reviews(self):
        def add_top_review():
            self.add_published_review(create_destination(self.country, self.unique("Ville")))

        self.assert_constant_queries(reverse("home"), add_top_review)
