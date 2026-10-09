from datetime import timedelta
from decimal import Decimal

from django.template.defaultfilters import date as format_date
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.tests.factories import create_country, create_destination
from promotions.models import Base, Scope
from promotions.tests.factories import create_promotion


class PublicPromotionsTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.japan = create_country()
        self.kyoto = create_destination(self.japan, "Kyoto")
        self.lisbon = create_destination(create_country("Portugal"), "Lisbonne")

    def test_offers_page_lists_only_running_automatic_promotions(self):
        create_promotion(name="Semaine du Japon", scope=Scope.COUNTRIES, countries=[self.japan])
        create_promotion(name="Code secret", code="BIENVENUE15")
        create_promotion(name="Offre désactivée", is_active=False)
        create_promotion(name="Offre à venir", starts_on=self.today + timedelta(days=1))
        create_promotion(
            name="Offre terminée", starts_on=self.today - timedelta(days=10), ends_on=self.today - timedelta(days=1)
        )

        response = self.client.get(reverse("offers"))

        self.assertContains(response, "Semaine du Japon")
        self.assertContains(response, "Pour : Japon")
        for hidden in ["Code secret", "BIENVENUE15", "Offre désactivée", "Offre à venir", "Offre terminée"]:
            self.assertNotContains(response, hidden)

    def test_offers_page_hides_promotion_on_withdrawn_destination(self):
        withdrawn = create_destination(self.japan, "Nara", active=False)
        create_promotion(name="Printemps à Nara", scope=Scope.DESTINATIONS, destinations=[withdrawn])

        self.assertNotContains(self.client.get(reverse("offers")), "Printemps à Nara")

    def test_banner_on_targeted_destination_with_terms(self):
        departure_from = self.today + timedelta(days=60)
        departure_until = self.today + timedelta(days=90)
        create_promotion(
            name="Semaine du Japon",
            value=Decimal("15"),
            base=Base.STAY,
            scope=Scope.COUNTRIES,
            countries=[self.japan],
            departure_from=departure_from,
            departure_until=departure_until,
        )

        response = self.client.get(reverse("destination_detail", args=[self.kyoto.pk]))

        self.assertContains(response, "-15 % sur le séjour</strong> jusqu'au")
        self.assertContains(
            response,
            f"pour les départs du {format_date(departure_from, 'j F Y')} au {format_date(departure_until, 'j F Y')}",
        )
        other_country = self.client.get(reverse("destination_detail", args=[self.lisbon.pk]))
        self.assertNotContains(other_country, "Semaine du Japon")

    def test_code_promotion_never_shown_on_destination(self):
        create_promotion(name="Code secret", code="BIENVENUE15")

        self.assertNotContains(self.client.get(reverse("destination_detail", args=[self.kyoto.pk])), "Code secret")
        self.assertNotContains(self.client.get(reverse("destination_list")), "badge-promo")

    def test_promo_label_only_on_targeted_destination_cards(self):
        create_promotion(scope=Scope.DESTINATIONS, destinations=[self.kyoto])

        response = self.client.get(reverse("destination_list"))

        self.assertEqual(
            [destination.has_promotion for destination in response.context["destinations"]], [True, False]
        )
        self.assertContains(response, '<span class="badge-promo">Promo</span>', count=1)
