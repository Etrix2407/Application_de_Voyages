from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_client
from catalog.tests.factories import create_country, create_destination
from dashboard.services.periods import custom_period
from dashboard.services.promotion_figures import promotion_figures
from dashboard.services.review_figures import MIN_REVIEWS_TO_RANK, review_figures
from orders.models import OrderStatus
from orders.tests.factories import create_order
from promotions.tests.factories import create_promotion
from reviews.models import ReviewStatus
from reviews.tests.factories import create_review, create_trip_done

MARCH = custom_period(date(2026, 3, 1), date(2026, 3, 31))


def brussels(day: date) -> datetime:
    return timezone.make_aware(datetime(day.year, day.month, day.day, 12))


class PromotionFiguresTests(TestCase):
    def setUp(self):
        self.client_account = create_client()
        self.destination = create_destination(create_country())

    def order(self, promotion, **fields):
        return create_order(self.client_account, self.destination, promotion=promotion, **fields)

    def test_running_promotions_exclude_cancelled_and_use_latest_discount(self):
        today = timezone.localdate()
        promotion = create_promotion(name="Printemps", starts_on=today - timedelta(days=400))
        unused = create_promotion(name="Sans succès")
        create_promotion(name="Terminée", starts_on=today - timedelta(days=10), ends_on=today - timedelta(days=1))
        # Cumul depuis le début : une commande d'il y a un an compte, quelle que soit la période.
        self.order(promotion, discount=Decimal("50"), created_at=timezone.now() - timedelta(days=365))
        self.order(promotion, discount=Decimal("50"), confirmed_discount=Decimal("30"), status=OrderStatus.CONFIRMED)
        self.order(promotion, discount=Decimal("100"), status=OrderStatus.CANCELLED)

        running = {figure.name: figure for figure in promotion_figures(MARCH).running}

        self.assertEqual(set(running), {"Printemps", "Sans succès"})
        self.assertEqual((running["Printemps"].order_count, running["Printemps"].total_discount), (2, Decimal("80")))
        self.assertEqual((running["Sans succès"].pk, running["Sans succès"].order_count), (unused.pk, 0))
        self.assertEqual(running["Sans succès"].total_discount, Decimal("0.00"))

    def test_best_promotion_counts_kept_orders_of_the_period(self):
        popular = create_promotion(name="Populaire")
        cancelled_often = create_promotion(name="Souvent annulée")
        for _ in range(2):
            self.order(popular, created_at=brussels(date(2026, 3, 10)))
            self.order(cancelled_often, created_at=brussels(date(2026, 3, 10)), status=OrderStatus.CANCELLED)
        self.order(cancelled_often, created_at=brussels(date(2026, 3, 10)))
        # Hors période : ne compte pas.
        for _ in range(3):
            self.order(cancelled_often, created_at=brussels(date(2026, 4, 2)))

        best = promotion_figures(MARCH).best

        self.assertEqual((best.pk, best.name, best.order_count), (popular.pk, "Populaire", 2))

    def test_no_promotion_used_in_the_period(self):
        self.order(create_promotion(), created_at=brussels(date(2026, 4, 2)))

        self.assertIsNone(promotion_figures(MARCH).best)


class ReviewFiguresTests(TestCase):
    def setUp(self):
        self.client_account = create_client()
        self.country = create_country()

    def review(self, destination, rating=5, published_at=None, **fields):
        fields.setdefault("status", ReviewStatus.PUBLISHED)
        order = create_trip_done(self.client_account, destination)
        return create_review(order, rating=rating, published_at=published_at or brussels(date(2026, 1, 5)), **fields)

    def test_average_and_published_count_compared_to_previous_period(self):
        destination = create_destination(self.country)
        self.review(destination, 5, brussels(date(2026, 3, 2)))
        # 31 mars à 23 h 30 UTC = 1er avril à Bruxelles : hors période.
        self.review(destination, 4, datetime(2026, 3, 31, 23, 30, tzinfo=dt_timezone.utc))
        self.review(destination, 4, brussels(date(2026, 2, 15)))
        self.review(destination, 1, status=ReviewStatus.PENDING)

        figures = review_figures(MARCH)

        self.assertEqual(figures.average_text, "4,3 / 5")
        self.assertEqual(figures.published_count, 1)
        self.assertEqual(figures.comparison.text, "0 %")

    def test_no_published_review(self):
        self.assertEqual(review_figures(MARCH).average_text, "Pas encore d'avis")

    def test_rankings_need_enough_reviews_and_never_repeat_a_destination(self):
        ratings = {"Kyoto": 5, "Nara": 4, "Osaka": 3, "Tokyo": 2}
        for name, rating in ratings.items():
            destination = create_destination(self.country, name)
            for _ in range(MIN_REVIEWS_TO_RANK):
                self.review(destination, rating)
        too_few = create_destination(self.country, "Sapporo")
        for _ in range(MIN_REVIEWS_TO_RANK - 1):
            self.review(too_few, 1)

        figures = review_figures(MARCH)

        self.assertEqual([d.name for d in figures.best_rated], ["Kyoto", "Nara", "Osaka"])
        # Quatre destinations classées : les moins bien notées ne reprennent pas les trois premières.
        self.assertEqual([d.name for d in figures.worst_rated], ["Tokyo"])
        self.assertEqual((figures.worst_rated[0].average, figures.worst_rated[0].review_count), (Decimal("2.0"), 5))


class PromotionsReviewsSectionTests(TestCase):
    def test_page_links_each_running_promotion(self):
        cache.clear()
        promotion = create_promotion(name="Semaine du Portugal")
        self.client.force_login(create_admin())

        response = self.client.get(reverse("pilotage_dashboard"))

        self.assertContains(response, reverse("manage_promotion_detail", args=[promotion.pk]))
        self.assertContains(response, "Aucune commande avec une promotion sur la période.")
        self.assertContains(response, "Pas encore d&#x27;avis")
