from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from reviews.models import Review, ReviewStatus

from .factories import create_review, create_trip_done


class StaffReviewListTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.url = reverse("manage_reviews")
        self.japan = create_country("Japon")
        self.peru = create_country("Pérou")
        self.kyoto = create_destination(self.japan, "Kyoto")
        self.cusco = create_destination(self.peru, "Cusco")
        self.numbers = iter(range(1, 100))

    def review(self, destination, title, departure=date(2026, 3, 1), written_days_ago=1, **fields):
        number = next(self.numbers)
        client = create_client(email=f"client{number}@example.com")
        return_date = departure + timedelta(days=7)
        trip = create_trip_done(client, destination, departure_date=departure, return_date=return_date)
        review = create_review(trip, title=title, **fields)
        Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - timedelta(days=written_days_ago))
        return review

    def titles(self, **filters):
        response = self.client.get(self.url, filters)
        return [review.title for review in response.context["page"].object_list]

    def test_all_reviews_newest_first(self):
        self.review(self.kyoto, "Ancien", written_days_ago=5)
        self.review(self.cusco, "Récent", written_days_ago=1, status=ReviewStatus.PUBLISHED)

        self.assertEqual(self.titles(), ["Récent", "Ancien"])

    def test_filter_by_status_country_destination_and_rating(self):
        self.review(self.kyoto, "Kyoto publié", status=ReviewStatus.PUBLISHED, rating=4)
        self.review(self.kyoto, "Kyoto attente", rating=5)
        self.review(self.cusco, "Cusco", rating=4)

        self.assertEqual(self.titles(status=ReviewStatus.PUBLISHED), ["Kyoto publié"])
        self.assertEqual(sorted(self.titles(country=self.japan.pk)), ["Kyoto attente", "Kyoto publié"])
        self.assertEqual(self.titles(destination=self.cusco.pk), ["Cusco"])
        self.assertEqual(sorted(self.titles(rating=4)), ["Cusco", "Kyoto publié"])

    def test_negative_reviews_filter_and_badge(self):
        self.review(self.kyoto, "Déçu", rating=2, comment="Hôtel bruyant.")
        self.review(self.kyoto, "Content", rating=4)

        self.assertEqual(self.titles(negative_only="on"), ["Déçu"])
        self.assertContains(self.client.get(self.url), 'class="badge-negative"', count=1)

    def test_two_periods_review_date_and_stay_date(self):
        self.review(self.kyoto, "Séjour de mars, écrit il y a 40 jours", departure=date(2026, 3, 10),
                    written_days_ago=40)
        self.review(self.kyoto, "Séjour de juillet, écrit hier", departure=date(2026, 7, 10), written_days_ago=1)
        last_week = (timezone.localdate() - timedelta(days=7)).isoformat()

        self.assertEqual(self.titles(written_from=last_week), ["Séjour de juillet, écrit hier"])
        self.assertEqual(
            self.titles(stay_from="2026-03-01", stay_to="2026-03-31"), ["Séjour de mars, écrit il y a 40 jours"]
        )

    def test_period_end_before_start_refused(self):
        response = self.client.get(self.url, {"stay_from": "2026-05-01", "stay_to": "2026-04-01"})

        self.assertContains(response, "La fin de la période doit être après son début.")

    def test_real_client_shown_even_if_anonymous(self):
        review = self.review(self.kyoto, "Anonyme", anonymous=True)

        response = self.client.get(self.url)

        self.assertContains(response, f"{review.order.client.first_name} {review.order.client.last_name}")

    def test_pages_keep_the_filters(self):
        for number in range(26):
            self.review(self.kyoto, f"Avis {number}", status=ReviewStatus.PUBLISHED)

        response = self.client.get(self.url, {"status": ReviewStatus.PUBLISHED})

        self.assertEqual(len(response.context["page"].object_list), 25)
        self.assertContains(response, "status=published&amp;page=2")

    def test_reachable_from_moderation_queue(self):
        self.assertContains(self.client.get(reverse("manage_pending_reviews")), self.url)
