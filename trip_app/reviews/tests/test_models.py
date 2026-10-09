from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Status
from orders.services.status import cancel_by_staff
from orders.tests.factories import create_order
from reviews.models import ANONYMOUS_NAME, EDIT_PERIOD, RefusalReason, Review, ReviewStatus
from reviews.services.eligibility import can_review, reviewable_orders

from .factories import create_review, create_trip_done


class ReviewRulesTests(TestCase):
    def setUp(self):
        self.order = create_trip_done(create_client(), create_destination(create_country()))

    def assert_invalid(self, field, **fields):
        review = Review(order=self.order, **{"rating": 4, "title": "Bien", **fields})
        with self.assertRaises(ValidationError) as error:
            review.full_clean()
        self.assertIn(field, error.exception.message_dict)

    def test_valid_review(self):
        Review(order=self.order, rating=4, title="Très bien").full_clean()

    def test_rating_from_one_to_five(self):
        for rating in [0, 6]:
            with self.subTest(rating=rating):
                self.assert_invalid("rating", rating=rating)

    def test_rating_also_checked_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_review(self.order, rating=9)

    def test_title_required_and_limited(self):
        self.assert_invalid("title", title="")
        self.assert_invalid("title", title="a" * 101)

    def test_comment_limited_to_1000_characters(self):
        self.assert_invalid("comment", comment="a" * 1001)

    def test_comment_required_for_low_rating(self):
        for rating in [1, 2]:
            with self.subTest(rating=rating):
                self.assert_invalid("comment", rating=rating, comment="  ")
        Review(order=self.order, rating=3, title="Moyen").full_clean()

    def test_refusal_needs_a_reason_and_details_for_other(self):
        self.assert_invalid("refusal_reason", status=ReviewStatus.REFUSED)
        self.assert_invalid(
            "refusal_details", status=ReviewStatus.REFUSED, refusal_reason=RefusalReason.OTHER
        )

    def test_one_review_per_order(self):
        create_review(self.order)

        with self.assertRaises(IntegrityError), transaction.atomic():
            create_review(self.order)

    def test_order_with_review_cannot_be_deleted(self):
        create_review(self.order)

        with self.assertRaises(ProtectedError):
            self.order.delete()

    def test_editable_for_thirty_days_after_creation(self):
        review = create_review(self.order)

        self.assertTrue(review.can_be_changed_by_client(review.created_at + EDIT_PERIOD - timedelta(minutes=1)))
        self.assertFalse(review.can_be_changed_by_client(review.created_at + EDIT_PERIOD))

    def test_negative_from_two_stars(self):
        self.assertTrue(Review(rating=2).is_negative)
        self.assertFalse(Review(rating=3).is_negative)


class AuthorNameTests(TestCase):
    def setUp(self):
        self.destination = create_destination(create_country())

    def test_first_name_and_initial(self):
        julie = create_client(first_name="Julie", last_name="dupont")

        self.assertEqual(create_review(create_trip_done(julie, self.destination)).author_name, "Julie D.")

    def test_anonymous_by_choice(self):
        review = create_review(create_trip_done(create_client(), self.destination), anonymous=True)

        self.assertEqual(review.author_name, ANONYMOUS_NAME)


class VerifiedTripTests(TestCase):
    """Seuls les clients réellement partis peuvent laisser un avis."""

    def setUp(self):
        self.marie = create_client()
        self.destination = create_destination(create_country())

    def test_confirmed_trip_with_past_return_can_be_reviewed(self):
        order = create_trip_done(self.marie, self.destination)

        self.assertTrue(can_review(self.marie, order))
        self.assertEqual(list(reviewable_orders(self.marie)), [order])

    def test_trips_not_done_cannot_be_reviewed(self):
        today = timezone.localdate()
        cases = {
            "en attente": create_order(self.marie, self.destination),
            "annulée": create_trip_done(self.marie, self.destination, status=Status.CANCELLED),
            "confirmée, à venir": create_order(self.marie, self.destination, status=Status.CONFIRMED),
            "retour aujourd'hui": create_trip_done(self.marie, self.destination, return_date=today),
        }
        for case, order in cases.items():
            with self.subTest(case=case):
                self.assertFalse(can_review(self.marie, order))

    def test_only_the_traveller_can_review(self):
        order = create_trip_done(self.marie, self.destination)

        self.assertFalse(can_review(create_client(email="paul@example.com"), order))

    def test_same_trip_another_year_is_another_review(self):
        create_review(create_trip_done(self.marie, self.destination))
        next_trip = create_trip_done(
            self.marie,
            self.destination,
            departure_date=timezone.localdate() - timedelta(days=5),
            return_date=timezone.localdate() - timedelta(days=1),
        )

        self.assertTrue(can_review(self.marie, next_trip))


class CancelledTripTests(TestCase):
    def test_review_hidden_when_confirmed_trip_is_cancelled(self):
        order = create_trip_done(create_client(), create_destination(create_country()))
        review = create_review(order, status=ReviewStatus.PUBLISHED)

        cancel_by_staff(order, create_agent(), "Voyage non effectué.")

        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.REFUSED)
        self.assertEqual(review.refusal_reason, RefusalReason.TRIP_CANCELLED)
        self.assertNotIn(review, Review.objects.public())

    def test_other_reviews_untouched(self):
        destination = create_destination(create_country())
        kept = create_review(create_trip_done(create_client(), destination), status=ReviewStatus.PUBLISHED)
        cancelled_order = create_order(create_client(email="paul@example.com"), destination)

        cancel_by_staff(cancelled_order, create_agent(), "Doublon.")

        kept.refresh_from_db()
        self.assertEqual(kept.status, ReviewStatus.PUBLISHED)


class PublicReviewsTests(TestCase):
    def setUp(self):
        self.country = create_country()
        self.destination = create_destination(self.country)
        order = create_trip_done(create_client(), self.destination)
        self.review = create_review(order, status=ReviewStatus.PUBLISHED)

    def test_only_published_reviews_are_public(self):
        pending = create_review(create_trip_done(create_client(email="paul@example.com"), self.destination))

        self.assertEqual(list(Review.objects.public()), [self.review])
        self.assertNotIn(pending, Review.objects.public())

    def test_hidden_while_destination_or_country_inactive_and_back_after(self):
        for item in [self.destination, self.country]:
            with self.subTest(item=item):
                item.active = False
                item.save()
                self.assertFalse(Review.objects.public().exists())

                item.active = True
                item.save()
                self.assertTrue(Review.objects.public().exists())
