from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Order, Status
from orders.services import promotions as messages
from orders.services.placing import parts_for
from orders.services.promotions import choose_promotion
from promotions.models import Base, Kind, Promotion, Scope
from promotions.tests.factories import create_promotion

from .factories import create_order, departure_in, review_tokens


class ChoosePromotionTests(TestCase):
    """Règles du choix : meilleure offre, limites, messages du code."""

    def setUp(self):
        cache.clear()
        self.marie = create_client()
        self.kyoto = create_destination(create_country(), "Kyoto", price_from=Decimal("800"))
        self.departure = departure_in()

    def choose(self, code="", adults=1, children=0, destination=None):
        destination = destination or self.kyoto
        prices = parts_for(destination, [], adults, children)
        return choose_promotion(self.marie, destination, self.departure, prices, code)

    def test_discount_after_child_half_price(self):
        create_promotion(value=Decimal("10"))

        # 800 € (adulte) + 400 € (enfant à 50 %) = 1 200 € ; -10 % = 120 €.
        self.assertEqual(self.choose(children=1).offer.discount, Decimal("120.00"))

    def test_best_automatic_offer_applied_without_code(self):
        create_promotion(name="-10 %", value=Decimal("10"))
        create_promotion(name="-100 €", kind=Kind.FIXED, value=Decimal("100"))

        self.assertEqual(self.choose().offer.promotion.name, "-100 €")

    def test_code_messages(self):
        today = timezone.localdate()
        create_promotion(code="FUTUR1", starts_on=today + timedelta(days=1))
        create_promotion(code="FINI01", starts_on=today - timedelta(days=9), ends_on=today - timedelta(days=1))
        create_promotion(code="ARRETE", is_active=False)
        create_promotion(code="PORTUGAL", scope=Scope.DESTINATIONS,
                         destinations=[create_destination(create_country("Portugal"), "Lisbonne")])
        create_promotion(code="AUTOMNE", departure_from=self.departure + timedelta(days=1),
                         departure_until=self.departure + timedelta(days=30))
        create_promotion(code="ACTIVITES", base=Base.ACTIVITIES)
        expected = {
            "INCONNU": messages.INVALID_CODE,
            "FUTUR1": messages.INVALID_CODE,
            "FINI01": messages.EXPIRED_CODE,
            "ARRETE": messages.NO_LONGER_AVAILABLE,
            "PORTUGAL": messages.WRONG_DESTINATION,
            "AUTOMNE": messages.WRONG_DEPARTURE,
            "ACTIVITES": messages.NOT_FOR_THIS_ORDER,
        }
        for code, message in expected.items():
            with self.subTest(code=code):
                self.assertEqual(self.choose(code).code_error, message)

    def test_limits_count_only_orders_not_cancelled(self):
        promotion = create_promotion(code="UNEFOIS", max_uses_per_client=1)
        order = create_order(self.marie, self.kyoto, promotion=promotion)

        self.assertEqual(self.choose("unefois").code_error, messages.ALREADY_USED)
        order.status = Status.CANCELLED
        order.save()
        self.assertTrue(self.choose("unefois").code_applied)

    def test_total_limit(self):
        promotion = create_promotion(code="CINQUANTE", max_uses=1)
        create_order(create_client(email="autre@example.com"), self.kyoto, promotion=promotion)

        self.assertEqual(self.choose("CINQUANTE").code_error, messages.NO_LONGER_AVAILABLE)

    def test_code_beaten_by_automatic_offer_is_not_used(self):
        create_promotion(name="Automatique", value=Decimal("20"))
        create_promotion(code="PETIT", value=Decimal("5"))

        choice = self.choose("PETIT")

        self.assertEqual(choice.offer.promotion.name, "Automatique")
        self.assertEqual(choice.code_note, "Une offre plus avantageuse s'applique déjà : -160,00 €")

    def test_wrong_codes_limited(self):
        create_promotion(code="BIENVENUE15")
        for attempt in range(10):
            self.choose(f"FAUX{attempt}")

        self.assertEqual(self.choose("BIENVENUE15").code_error, messages.TOO_MANY_WRONG_CODES)


class OrderWithPromotionTests(TestCase):
    """Parcours réel du client : vérification, envoi, récapitulatif."""

    def setUp(self):
        cache.clear()
        self.marie = create_client()
        self.client.force_login(self.marie)
        self.kyoto = create_destination(create_country(), "Kyoto", price_from=Decimal("1000"))
        self.url = reverse("create_order", args=[self.kyoto.pk])
        departure = departure_in()
        self.data = {
            "departure_date": departure.isoformat(),
            "return_date": (departure + timedelta(days=7)).isoformat(),
            "adults": "2",
            "children": "0",
            "remarks": "",
            "promo_code": "",
        }

    def test_code_applied_and_frozen_in_the_order(self):
        promotion = create_promotion(name="Bienvenue", code="BIENVENUE", kind=Kind.FIXED, value=Decimal("100"))

        review = self.client.post(self.url, {**self.data, "promo_code": "bienvenue"})
        self.client.post(self.url, {**self.data, "promo_code": "bienvenue", **review_tokens(review), "confirm": ""})
        promotion.name = "Nouveau nom"
        promotion.save()

        order = Order.objects.get()
        self.assertContains(review, "Code appliqué : -100,00 €")
        self.assertEqual((order.estimated_price, order.discount), (Decimal("1900.00"), Decimal("100.00")))
        page = self.client.get(reverse("my_order_detail", args=[order.pk]))
        self.assertContains(page, "2000,00 €")  # prix avant remise
        self.assertContains(page, "-100,00 € — Bienvenue")

    def test_refused_code_shown_on_the_form_and_nothing_sent(self):
        response = self.client.post(self.url, {**self.data, "promo_code": "INCONNU"})

        self.assertContains(response, "Code invalide")
        self.assertFalse(Order.objects.exists())

    def test_promotion_ended_after_review_shows_new_price(self):
        promotion = create_promotion(value=Decimal("10"))
        review = self.client.post(self.url, self.data)
        promotion.is_active = False
        promotion.save()

        response = self.client.post(self.url, {**self.data, **review_tokens(review), "confirm": ""})

        self.assertContains(response, "a changé depuis votre vérification")
        self.assertContains(response, "2000,00 €")
        self.assertFalse(Order.objects.exists())


class PublicOffersTests(TestCase):
    def test_exhausted_automatic_promotion_no_longer_shown(self):
        kyoto = create_destination(create_country(), "Kyoto")
        promotion = create_promotion(name="Dernières places", max_uses=1)
        order = create_order(create_client(), kyoto, promotion=promotion)

        self.assertNotContains(self.client.get(reverse("offers")), "Dernières places")
        order.status = Status.CANCELLED
        order.save()
        self.assertContains(self.client.get(reverse("offers")), "Dernières places")


class ConfirmationTests(TestCase):
    def test_discount_reapplied_to_the_recalculated_price(self):
        kyoto = create_destination(create_country(), "Kyoto", price_from=Decimal("1000"))
        promotion = create_promotion(value=Decimal("10"))
        order = create_order(create_client(), kyoto, adults=1, promotion=promotion, promotion_name=promotion.name,
                             estimated_price=Decimal("900"), discount=Decimal("100"))
        kyoto.price_from = Decimal("1200")
        kyoto.save()
        self.client.force_login(create_agent())

        self.client.post(reverse("manage_confirm_order", args=[order.pk]))

        order.refresh_from_db()
        self.assertEqual((order.confirmed_price, order.confirmed_discount), (Decimal("1080.00"), Decimal("120.00")))


class UsedPromotionTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin())
        self.promotion = create_promotion(value=Decimal("10"))
        create_order(create_client(), create_destination(create_country()), promotion=self.promotion)

    def test_only_name_description_and_end_date_can_change(self):
        today = timezone.localdate()
        data = {
            "name": "Nouveau nom", "description": "", "kind": "fixed", "value": "50", "scope": "catalog",
            "base": "stay", "starts_on": today.isoformat(), "ends_on": (today + timedelta(days=5)).isoformat(),
        }

        self.client.post(reverse("manage_edit_promotion", args=[self.promotion.pk]), data)

        self.promotion.refresh_from_db()
        self.assertEqual(self.promotion.name, "Nouveau nom")
        self.assertEqual(self.promotion.ends_on, today + timedelta(days=5))
        self.assertEqual((self.promotion.kind, self.promotion.value), (Kind.PERCENT, Decimal("10")))

    def test_cannot_be_deleted(self):
        response = self.client.post(reverse("manage_delete_promotion", args=[self.promotion.pk]), follow=True)

        self.assertContains(response, "déjà été utilisée")
        self.assertTrue(Promotion.objects.filter(pk=self.promotion.pk).exists())
