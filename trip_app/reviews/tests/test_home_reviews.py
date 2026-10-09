from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_client
from catalog.tests.factories import create_country, create_destination
from reviews.models import ReviewStatus

from .factories import create_review, create_trip_done


class HomeTopReviewsTests(TestCase):
    def setUp(self):
        self.destination = create_destination(create_country(), "Kyoto")
        self.numbers = iter(range(1, 100))

    def review(self, title, rating=5, days_ago=1, destination=None, **fields):
        number = next(self.numbers)
        client = create_client(email=f"client{number}@example.com", first_name="Julie", last_name="Dupont")
        fields.setdefault("status", ReviewStatus.PUBLISHED)
        fields.setdefault("comment", "" if rating > 2 else "Décevant.")
        return create_review(
            create_trip_done(client, destination or self.destination),
            title=title,
            rating=rating,
            published_at=timezone.now() - timedelta(days=days_ago),
            **fields,
        )

    def top_titles(self):
        return [review.title for review in self.client.get(reverse("home")).context["top_reviews"]]

    def test_no_section_without_five_star_reviews(self):
        self.review("Bien", rating=4)

        self.assertNotContains(self.client.get(reverse("home")), "Ils sont partis avec nous")

    def test_five_latest_five_star_reviews_newest_first(self):
        for days_ago in range(1, 8):
            self.review(f"Parfait {days_ago}", days_ago=days_ago)

        self.assertEqual(self.top_titles(), [f"Parfait {days_ago}" for days_ago in range(1, 6)])

    def test_only_published_five_star_reviews(self):
        self.review("Cinq étoiles")
        self.review("Quatre étoiles", rating=4)
        self.review("En attente", status=ReviewStatus.PENDING)

        self.assertEqual(self.top_titles(), ["Cinq étoiles"])

    def test_reviews_of_inactive_destination_excluded(self):
        closed = create_destination(self.destination.country, "Osaka", active=False)
        self.review("Osaka parfait", destination=closed)

        self.assertEqual(self.top_titles(), [])

    def test_section_shows_verified_review_and_link(self):
        self.review("Inoubliable", comment="Un guide formidable.")

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Ils sont partis avec nous")
        self.assertContains(response, "✓ Voyage vérifié")
        self.assertContains(response, "Julie D.")
        self.assertContains(response, reverse("destination_detail", args=[self.destination.pk]) + "#avis")
