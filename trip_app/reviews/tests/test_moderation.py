from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Status
from reviews.models import RefusalReason, Review, ReviewStatus
from reviews.services.moderation import ModerationNotAllowed, hide, pending_reviews, publish, refuse
from reviews.services.writing import update_review

from .factories import create_review, create_trip_done


class ModerationQueueTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.destination = create_destination(create_country(), "Kyoto")
        self.url = reverse("manage_pending_reviews")

    def review_by(self, email, days_ago, **fields):
        trip = create_trip_done(create_client(email=email), self.destination)
        return create_review(trip, submitted_at=timezone.now() - timedelta(days=days_ago), **fields)

    def test_oldest_first_and_only_pending(self):
        recent = self.review_by("recent@example.com", 1, title="Récent")
        old = self.review_by("ancien@example.com", 5, title="Ancien")
        self.review_by("publie@example.com", 9, title="Déjà publié", status=ReviewStatus.PUBLISHED)

        response = self.client.get(self.url)

        self.assertEqual(list(response.context["reviews"]), [old, recent])
        self.assertNotContains(response, "Déjà publié")

    def test_negative_reviews_highlighted(self):
        self.review_by("negatif@example.com", 1, rating=2, comment="Hôtel bruyant.")

        self.assertContains(self.client.get(self.url), "Avis négatif")

    def test_counter_in_staff_menu(self):
        self.review_by("a@example.com", 1)
        self.review_by("b@example.com", 2)

        for staff in [create_agent(email="autre@example.com"), create_admin()]:
            with self.subTest(role=staff.role):
                self.client.force_login(staff)
                self.assertContains(self.client.get(reverse("home")), "Avis à modérer (2)")

    def test_no_counter_for_clients(self):
        self.client.force_login(create_client(email="marie@example.com"))

        self.assertNotContains(self.client.get(reverse("home")), "Avis à modérer")


class ModerationActionsTests(TestCase):
    def setUp(self):
        self.client.force_login(create_agent())
        self.julie = create_client(first_name="Julie", last_name="Dupont")
        self.trip = create_trip_done(self.julie, create_destination(create_country(), "Kyoto"))
        self.review = create_review(self.trip, title="Superbe", anonymous=True)

    def version(self):
        self.review.refresh_from_db()
        return self.review.version

    def refused(self, **data):
        url = reverse("manage_refuse_review", args=[self.review.pk])
        return self.client.post(url, {"version": self.version(), **data}, follow=True)

    def published(self):
        url = reverse("manage_publish_review", args=[self.review.pk])
        return self.client.post(url, {"version": self.version()}, follow=True)

    def test_staff_sees_real_client_and_order_even_if_anonymous(self):
        response = self.client.get(reverse("manage_review_detail", args=[self.review.pk]))

        self.assertContains(response, "Julie Dupont")
        self.assertContains(response, "Voyageur anonyme")
        self.assertContains(response, reverse("manage_order_detail", args=[self.trip.pk]))

    def test_publish(self):
        response = self.published()

        self.assertContains(response, "est publié")
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PUBLISHED)
        self.assertIsNotNone(self.review.published_at)
        self.assertIn(self.review, Review.objects.public())

    def test_publish_only_by_post(self):
        self.assertEqual(self.client.get(reverse("manage_publish_review", args=[self.review.pk])).status_code, 405)

    def test_refuse_requires_a_reason(self):
        response = self.refused(reason="", details="")

        self.assertContains(response, "Le motif est obligatoire.")
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)

    def test_other_reason_requires_details(self):
        self.assertContains(self.refused(reason=RefusalReason.OTHER, details=" "), "Précisez le motif")

    def test_refuse_with_reason_visible_to_client(self):
        self.refused(reason=RefusalReason.PERSONAL_DATA, details="Numéro de téléphone du guide.")

        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.REFUSED)
        self.client.force_login(self.julie)
        page = self.client.get(reverse("my_reviews"))
        self.assertContains(page, "Contient des coordonnées personnelles")
        self.assertContains(page, "Numéro de téléphone du guide.")

    def test_trip_cancelled_reason_not_offered(self):
        response = self.client.get(reverse("manage_refuse_review", args=[self.review.pk]))

        self.assertNotContains(response, "Voyage annulé")

    def test_hide_published_review(self):
        publish(self.review)

        response = self.refused(reason=RefusalReason.ABUSIVE)

        self.assertContains(response, "est masqué")
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.REFUSED)
        self.assertEqual(self.review.refusal_reason, RefusalReason.ABUSIVE)
        self.assertNotIn(self.review, Review.objects.public())

    def test_text_never_changed_by_staff(self):
        self.client.post(
            reverse("manage_refuse_review", args=[self.review.pk]),
            {"reason": RefusalReason.OFF_TOPIC, "title": "Modifié", "comment": "Modifié"},
        )

        self.review.refresh_from_db()
        self.assertEqual(self.review.title, "Superbe")

    def test_client_cannot_moderate(self):
        self.client.force_login(self.julie)

        self.assertEqual(self.client.post(reverse("manage_publish_review", args=[self.review.pk])).status_code, 403)
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)


class ModerationServiceTests(TestCase):
    def setUp(self):
        self.trip = create_trip_done(create_client(), create_destination(create_country()))
        self.review = create_review(self.trip)

    def test_cannot_publish_twice(self):
        publish(self.review)

        with self.assertRaises(ModerationNotAllowed):
            publish(self.review)

    def test_cannot_hide_a_pending_review(self):
        with self.assertRaises(ModerationNotAllowed):
            hide(self.review, RefusalReason.ABUSIVE)

    def test_cannot_publish_review_of_cancelled_trip(self):
        self.trip.status = Status.CANCELLED
        self.trip.save()

        with self.assertRaises(ModerationNotAllowed):
            publish(self.review)

    def test_invalid_reasons_refused(self):
        for reason in ["", "inconnu", RefusalReason.TRIP_CANCELLED, RefusalReason.OTHER]:
            with self.subTest(reason=reason), self.assertRaises(ValueError):
                refuse(self.review, reason, details="")

    def test_edited_review_goes_to_the_end_of_the_queue(self):
        older = create_review(create_trip_done(create_client(email="b@example.com"), self.trip.destination))
        Review.objects.filter(pk=older.pk).update(submitted_at=timezone.now() - timedelta(days=3))
        Review.objects.filter(pk=self.review.pk).update(submitted_at=timezone.now() - timedelta(days=5))
        self.review.refresh_from_db()

        update_review(self.review)

        self.assertEqual(list(pending_reviews()), [older, self.review])


class ReviewedVersionTests(TestCase):
    """L'agent publie ou refuse la version qu'il a lue, jamais une version modifiée entre-temps."""

    def setUp(self):
        self.client.force_login(create_agent())
        self.julie = create_client()
        self.review = create_review(create_trip_done(self.julie, create_destination(create_country())), title="Anodin")
        self.seen = self.review.version  # version affichée à l'agent

    def client_edits_meanwhile(self):
        self.review.title = "Version jamais relue"
        update_review(self.review)

    def test_publish_refused_if_client_edited_meanwhile(self):
        self.client_edits_meanwhile()

        response = self.client.post(
            reverse("manage_publish_review", args=[self.review.pk]), {"version": self.seen}, follow=True
        )

        self.assertContains(response, "relisez-le")
        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)

    def test_refusal_refused_if_client_edited_meanwhile(self):
        self.client_edits_meanwhile()

        self.client.post(
            reverse("manage_refuse_review", args=[self.review.pk]),
            {"version": self.seen, "reason": RefusalReason.OFF_TOPIC},
        )

        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)

    def test_publish_without_version_refused(self):
        self.client.post(reverse("manage_publish_review", args=[self.review.pk]))

        self.review.refresh_from_db()
        self.assertEqual(self.review.status, ReviewStatus.PENDING)

    def test_detail_page_carries_the_version_it_shows(self):
        response = self.client.get(reverse("manage_review_detail", args=[self.review.pk]))

        self.assertContains(response, f'name="version" value="{self.seen}"')
