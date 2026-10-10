from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Status
from orders.services.status import cancel_by_staff
from orders.tests.factories import create_order
from reviews.models import EDIT_PERIOD, RefusalReason, Review, ReviewStatus
from reviews.services.writing import update_review

from .factories import create_review, create_trip_done

GOOD_REVIEW = {"rating": "5", "title": "Un séjour inoubliable", "comment": "Guide formidable.", "anonymous": ""}


def age_beyond_edit_period(review):
    """L'avis a été créé il y a 30 jours : il n'est plus modifiable."""
    Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - EDIT_PERIOD)


class WriteReviewTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.destination = create_destination(create_country(), "Kyoto")
        self.trip = create_trip_done(self.marie, self.destination)
        self.url = reverse("create_review", args=[self.trip.pk])

    def test_menu_and_order_detail_invite_to_review(self):
        self.assertContains(self.client.get(reverse("home")), reverse("my_reviews"))
        self.assertContains(self.client.get(reverse("my_order_detail", args=[self.trip.pk])), self.url)
        self.assertContains(self.client.get(reverse("my_reviews")), self.url)

    def test_review_saved_pending_validation(self):
        response = self.client.post(self.url, GOOD_REVIEW, follow=True)

        self.assertContains(response, "sera publié après sa validation")
        review = Review.objects.get()
        self.assertEqual((review.order, review.rating, review.status), (self.trip, 5, ReviewStatus.PENDING))
        self.assertNotIn(review, Review.objects.public())

    def test_trip_not_done_cannot_be_reviewed(self):
        upcoming = create_order(self.marie, self.destination, status=Status.CONFIRMED)
        url = reverse("create_review", args=[upcoming.pk])

        self.assertNotContains(self.client.get(reverse("my_order_detail", args=[upcoming.pk])), url)
        response = self.client.post(url, GOOD_REVIEW, follow=True)

        self.assertContains(response, "après votre retour")
        self.assertFalse(Review.objects.exists())

    def test_second_review_on_same_trip_refused(self):
        self.client.post(self.url, GOOD_REVIEW)

        self.client.post(self.url, {**GOOD_REVIEW, "title": "Encore"})

        self.assertEqual(Review.objects.count(), 1)

    def test_other_client_trip_not_found(self):
        self.client.force_login(create_client(email="paul@example.com"))

        self.assertEqual(self.client.get(self.url).status_code, 404)


class MyReviewsTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.trip = create_trip_done(self.marie, create_destination(create_country(), "Kyoto"))

    def test_status_and_refusal_reason_shown(self):
        create_review(
            self.trip,
            title="Mon voyage",
            status=ReviewStatus.REFUSED,
            refusal_reason=RefusalReason.OTHER,
            refusal_details="Merci de retirer le nom du guide.",
        )

        response = self.client.get(reverse("my_reviews"))

        self.assertContains(response, "Mon voyage")
        self.assertContains(response, "Refusé")
        self.assertContains(response, "Merci de retirer le nom du guide.")

    def test_only_own_reviews(self):
        paul = create_client(email="paul@example.com")
        create_review(create_trip_done(paul, self.trip.destination), title="Avis de Paul")

        self.assertNotContains(self.client.get(reverse("my_reviews")), "Avis de Paul")


class EditReviewTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.trip = create_trip_done(self.marie, create_destination(create_country(), "Kyoto"))

    def edit(self, review, **fields):
        return self.client.post(reverse("edit_review", args=[review.pk]), {**GOOD_REVIEW, **fields}, follow=True)

    def test_published_review_goes_back_to_moderation_and_is_hidden(self):
        review = create_review(self.trip, status=ReviewStatus.PUBLISHED)

        response = self.edit(review, title="Avis corrigé")

        self.assertContains(response, "de nouveau publié après validation")
        review.refresh_from_db()
        self.assertEqual((review.title, review.status), ("Avis corrigé", ReviewStatus.PENDING))
        self.assertNotIn(review, Review.objects.public())

    def test_refused_review_corrected_goes_back_to_moderation(self):
        review = create_review(
            self.trip, status=ReviewStatus.REFUSED, refusal_reason=RefusalReason.OFF_TOPIC
        )

        self.edit(review)

        review.refresh_from_db()
        self.assertEqual((review.status, review.refusal_reason), (ReviewStatus.PENDING, ""))

    def test_locked_after_thirty_days(self):
        review = create_review(self.trip, title="Avant")

        age_beyond_edit_period(review)

        response = self.edit(review, title="Après")
        page = self.client.get(reverse("my_reviews"))

        self.assertContains(response, "ne peut plus être modifié")
        self.assertContains(page, "Plus modifiable")
        review.refresh_from_db()
        self.assertEqual(review.title, "Avant")

    def test_review_of_cancelled_trip_cannot_be_republished(self):
        review = create_review(self.trip, status=ReviewStatus.PUBLISHED)
        self.trip.status = Status.CANCELLED
        self.trip.save()

        self.edit(review)

        review.refresh_from_db()
        self.assertEqual(review.status, ReviewStatus.PUBLISHED)

    def test_trip_cancelled_meanwhile_not_overwritten(self):
        review = create_review(self.trip, status=ReviewStatus.PUBLISHED, title="Avant")

        def cancel_then_update(*args, **kwargs):
            # L'agence annule le voyage pendant que le client envoie sa modification.
            cancel_by_staff(self.trip, create_agent(), "Voyage non effectué.")
            return update_review(*args, **kwargs)

        with mock.patch("reviews.views.client.update_review", side_effect=cancel_then_update):
            response = self.edit(review, title="Après")

        self.assertContains(response, "ne peut plus être modifié")
        review.refresh_from_db()
        self.assertEqual(
            (review.title, review.status, review.refusal_reason),
            ("Avant", ReviewStatus.REFUSED, RefusalReason.TRIP_CANCELLED),
        )

    def test_other_client_review_not_found(self):
        review = create_review(self.trip)
        self.client.force_login(create_client(email="paul@example.com"))

        self.assertEqual(self.client.get(reverse("edit_review", args=[review.pk])).status_code, 404)


class DeleteReviewTests(TestCase):
    def setUp(self):
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.review = create_review(create_trip_done(self.marie, create_destination(create_country())))
        self.url = reverse("remove_review", args=[self.review.pk])

    def test_get_asks_confirmation_without_deleting(self):
        self.assertContains(self.client.get(self.url), "définitive")
        self.assertTrue(Review.objects.exists())

    def test_deleted_and_trip_cannot_be_reviewed_again(self):
        # Sinon supprimer puis réécrire contournerait un refus et le délai de 30 jours.
        trip = self.review.order

        response = self.client.post(self.url, follow=True)
        self.client.post(reverse("create_review", args=[trip.pk]), GOOD_REVIEW)

        self.assertContains(response, "Votre avis a été supprimé.")
        self.assertNotContains(response, reverse("create_review", args=[trip.pk]))
        self.assertFalse(Review.objects.exists())

    def test_can_still_delete_after_thirty_days(self):
        age_beyond_edit_period(self.review)

        self.client.post(self.url)

        self.assertFalse(Review.objects.exists())

    def test_order_detail_shows_given_review(self):
        response = self.client.get(reverse("my_order_detail", args=[self.review.order.pk]))

        self.assertContains(response, "Votre avis sur ce voyage")
        self.assertContains(response, "En attente de validation")


class TripEndTests(TestCase):
    def test_trip_ending_today_not_yet_reviewable_from_page(self):
        marie = create_client()
        self.client.force_login(marie)
        trip = create_trip_done(marie, create_destination(create_country()), return_date=timezone.localdate())

        response = self.client.get(reverse("my_order_detail", args=[trip.pk]))

        self.assertNotContains(response, "Donner mon avis")
