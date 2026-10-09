from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_client
from catalog.models import FavoriteDestination
from catalog.tests.factories import create_country, create_destination
from reviews.models import ReviewStatus
from reviews.services.ratings import NO_REVIEWS, attach_ratings

from .factories import create_review, create_trip_done


class ReviewsMixin:
    def setUp(self):
        self.numbers = iter(range(1, 1000))
        self.country = create_country("Maroc")
        self.destination = create_destination(self.country, "Marrakech")

    def published(self, rating=5, destination=None, days_ago=1, **fields):
        number = next(self.numbers)
        client = create_client(email=f"client{number}@example.com", first_name="Julie", last_name="Dupont")
        trip = create_trip_done(client, destination or self.destination)
        fields.setdefault("title", f"Avis {number}")
        fields.setdefault("status", ReviewStatus.PUBLISHED)
        return create_review(trip, rating=rating, published_at=timezone.now() - timedelta(days=days_ago), **fields)


class RatingSummaryTests(ReviewsMixin, TestCase):
    def summary(self):
        return attach_ratings([self.destination])[0].rating_summary

    def test_average_rounded_to_one_decimal(self):
        for rating in [5, 5, 4]:
            self.published(rating)

        self.assertEqual((self.summary().average, self.summary().count), (Decimal("4.7"), 3))

    def test_only_published_reviews_count(self):
        self.published(5)
        waiting = create_trip_done(create_client(email="attente@example.com"), self.destination)
        create_review(waiting, rating=1, comment="x")
        self.published(1, comment="x", status=ReviewStatus.REFUSED, refusal_reason="abusive")

        self.assertEqual((self.summary().average, self.summary().count), (Decimal("5.0"), 1))

    def test_no_reviews(self):
        self.assertEqual(self.summary(), NO_REVIEWS)


class DestinationPageTests(ReviewsMixin, TestCase):
    def page(self, **params):
        return self.client.get(reverse("destination_detail", args=[self.destination.pk]), params)

    def test_without_reviews_never_shows_zero_stars(self):
        response = self.page()

        self.assertContains(response, "Pas encore d'avis")
        self.assertNotContains(response, "0 sur 5")

    def test_summary_and_verified_reviews(self):
        self.published(5, comment="Riad magnifique.")
        self.published(4)

        response = self.page()

        self.assertContains(response, "4,5 sur 5 (2 avis)")
        self.assertContains(response, "Riad magnifique.")
        self.assertContains(response, "✓ Voyage vérifié — séjour de")
        self.assertContains(response, "Julie D.")

    def test_anonymous_review(self):
        self.published(5, anonymous=True)

        response = self.page()

        self.assertContains(response, "Voyageur anonyme")
        self.assertNotContains(response, "Julie D.")

    def test_stay_month_and_publication_date(self):
        trip_review = self.published(5)
        trip_review.order.departure_date = date(2026, 3, 10)
        trip_review.order.save()

        self.assertContains(self.page(), "séjour de mars 2026")

    def test_newest_first_by_default_and_best_first_on_demand(self):
        old_good = self.published(5, days_ago=10, title="Ancien excellent")
        new_average = self.published(3, days_ago=1, title="Récent moyen")

        self.assertEqual(list(self.page().context["reviews_page"]), [new_average, old_good])
        self.assertEqual(list(self.page(tri="meilleures-notes").context["reviews_page"]), [old_good, new_average])

    def test_filter_by_stars(self):
        self.published(5, title="Cinq")
        self.published(2, comment="Bof", title="Deux")

        response = self.page(etoiles="2")

        self.assertContains(response, "Deux")
        self.assertNotContains(response, "Cinq")

    def test_pages_of_ten_keep_the_filters(self):
        for _ in range(11):
            self.published(5)

        response = self.page(tri="meilleures-notes")

        self.assertEqual(len(response.context["reviews_page"]), 10)
        self.assertContains(response, "tri=meilleures-notes&amp;page=2")

    def test_pending_and_refused_reviews_not_shown(self):
        create_review(create_trip_done(create_client(email="a@example.com"), self.destination), title="En attente")

        self.assertNotContains(self.page(), "En attente")


class DestinationListsTests(ReviewsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.published(5)
        self.published(4)
        self.quiet = create_destination(self.country, "Fès")

    def test_all_destinations_page_is_public(self):
        response = self.client.get(reverse("destination_list"))

        self.assertContains(response, "Marrakech")
        self.assertContains(response, "Maroc")
        self.assertContains(response, "4,5 sur 5 (2 avis)")
        self.assertContains(response, "Pas encore d'avis")

    def test_inactive_destination_and_its_reviews_hidden(self):
        self.destination.active = False
        self.destination.save()

        response = self.client.get(reverse("destination_list"))

        self.assertNotContains(response, "Marrakech")
        self.assertNotContains(response, "2 avis")

    def test_country_page_and_search_show_ratings(self):
        for url in [
            reverse("country_detail", args=[self.country.pk]),
            reverse("search") + "?keyword=marrakech",
        ]:
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "4,5 sur 5 (2 avis)")

    def test_favorites_show_ratings(self):
        marie = create_client(email="marie@example.com")
        FavoriteDestination.objects.create(client=marie, destination=self.destination)
        self.client.force_login(marie)

        self.assertContains(self.client.get(reverse("favorite_list")), "4,5 sur 5 (2 avis)")

    def test_menu_link(self):
        self.assertContains(self.client.get(reverse("home")), reverse("destination_list"))
