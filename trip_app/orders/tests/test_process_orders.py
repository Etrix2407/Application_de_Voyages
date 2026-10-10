from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.models import Order, Status, StatusChange
from orders.services.status import TransitionNotAllowed, cancel_by_client, cancel_by_staff, confirm_by_staff

from .factories import create_order


class StaffProcessingTests(TestCase):
    def setUp(self):
        self.agent = create_agent()
        self.client.force_login(self.agent)
        self.marie = create_client()
        self.order = create_order(self.marie, create_destination(create_country(), "Kyoto"))
        self.detail = reverse("manage_order_detail", args=[self.order.pk])
        self.confirm_url = reverse("manage_confirm_order", args=[self.order.pk])
        self.cancel_url = reverse("manage_cancel_order", args=[self.order.pk])

    def refreshed_status(self):
        self.order.refresh_from_db()
        return self.order.status

    def test_pending_order_offers_confirm_and_cancel(self):
        response = self.client.get(self.detail)

        self.assertContains(response, self.confirm_url)
        self.assertContains(response, self.cancel_url)

    def test_confirm_records_agent_in_history(self):
        response = self.client.post(self.confirm_url, follow=True)

        self.assertContains(response, "est confirmée")
        self.assertEqual(self.refreshed_status(), Status.CONFIRMED)
        change = self.order.history.get()
        self.assertEqual(
            (change.status, change.author, change.author_name), (Status.CONFIRMED, self.agent, "Luc Martin")
        )

    def test_confirmed_order_shows_cancel_only(self):
        confirm_by_staff(self.order, self.agent)

        response = self.client.get(self.detail)

        self.assertNotContains(response, self.confirm_url)
        self.assertContains(response, self.cancel_url)

    def test_staff_cancel_requires_reason(self):
        response = self.client.post(self.cancel_url, {"internal_reason": "   "})

        self.assertContains(response, "Le motif interne est obligatoire.")
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_staff_cancels_pending_order_with_reason_and_explanation(self):
        response = self.client.post(
            self.cancel_url,
            {"internal_reason": "Client injoignable.", "explanation": "Nous n'avons pas pu vous joindre."},
            follow=True,
        )

        self.assertContains(response, "est annulée")
        self.assertEqual(self.refreshed_status(), Status.CANCELLED)
        change = self.order.history.get()
        self.assertEqual(
            (change.author_name, change.internal_reason, change.reason),
            ("Luc Martin", "Client injoignable.", "Nous n'avons pas pu vous joindre."),
        )

    def test_staff_can_cancel_confirmed_order(self):
        confirm_by_staff(self.order, self.agent)

        self.client.post(self.cancel_url, {"internal_reason": "Le client a appelé pour annuler."})

        self.assertEqual(self.refreshed_status(), Status.CANCELLED)
        self.assertEqual(
            list(self.order.history.values_list("status", flat=True)), [Status.CONFIRMED, Status.CANCELLED]
        )

    def test_cancelled_order_offers_no_action(self):
        cancel_by_client(self.order)

        response = self.client.get(self.detail)

        self.assertNotContains(response, self.confirm_url)
        self.assertNotContains(response, self.cancel_url)

    def test_invalid_transitions_refused_with_message(self):
        cancel_by_client(self.order)

        confirm = self.client.post(self.confirm_url, follow=True)
        cancel = self.client.post(self.cancel_url, {"internal_reason": "Doublon."}, follow=True)

        self.assertContains(confirm, "Seule une demande en attente peut être confirmée.")
        self.assertContains(cancel, "Cette demande est déjà annulée.")
        self.assertEqual(self.order.history.count(), 1)

    def test_confirm_only_by_post(self):
        self.assertEqual(self.client.get(self.confirm_url).status_code, 405)
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_client_cannot_process_orders(self):
        self.client.force_login(self.marie)

        self.assertEqual(self.client.post(self.confirm_url).status_code, 403)
        self.assertEqual(self.client.post(self.cancel_url, {"internal_reason": "x"}).status_code, 403)
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_client_sees_explanation_but_not_internal_reason(self):
        cancel_by_staff(self.order, self.agent, "Hôtel partenaire en faillite.", "Destination fermée cette saison.")
        self.client.force_login(self.marie)

        response = self.client.get(reverse("my_order_detail", args=[self.order.pk]))

        self.assertContains(response, "Annulée")
        self.assertContains(response, "Destination fermée cette saison.")
        self.assertNotContains(response, "Hôtel partenaire en faillite.")
        self.assertNotContains(response, "Motif interne")
        self.assertContains(response, "Agence")
        self.assertNotContains(response, "Luc Martin")

    def test_client_sees_no_reason_without_explanation(self):
        cancel_by_staff(self.order, self.agent, "Hôtel partenaire en faillite.")
        self.client.force_login(self.marie)

        response = self.client.get(reverse("my_order_detail", args=[self.order.pk]))

        self.assertEqual(self.order.history.get().reason, "")
        self.assertNotContains(response, "Hôtel partenaire en faillite.")
        self.assertContains(response, "<td>—</td>", html=True)

    def test_client_or_agency_decided_by_who_acted_not_by_name(self):
        # Un agent qui s'appellerait « Client » reste affiché « Agence » au client.
        agent_named_client = StatusChange(author_name="Client", by_client=False)
        client_change = StatusChange(author_name="Client", by_client=True)

        self.assertEqual(agent_named_client.author_for_client, "Agence")
        self.assertEqual(client_change.author_for_client, "Client")

    def test_staff_sees_agent_name_and_internal_reason_in_history(self):
        cancel_by_staff(self.order, self.agent, "Hôtel partenaire en faillite.", "Destination fermée cette saison.")

        response = self.client.get(self.detail)

        self.assertContains(response, "Luc Martin")
        self.assertContains(response, "Hôtel partenaire en faillite.")
        self.assertContains(response, "Destination fermée cette saison.")

    def test_client_sees_own_actions_as_client(self):
        cancel_by_client(self.order)
        self.client.force_login(self.marie)

        response = self.client.get(reverse("my_order_detail", args=[self.order.pk]))

        self.assertContains(response, "<td>Client</td>", html=True)
        self.assertNotContains(response, "Agence")


class TransitionServiceTests(TestCase):
    def setUp(self):
        self.agent = create_agent()
        self.order = create_order(create_client(), create_destination(create_country()))

    def test_history_keeps_agent_name_after_agent_deletion(self):
        confirm_by_staff(self.order, self.agent)
        self.agent.delete()

        change = self.order.history.get()
        self.assertIsNone(change.author)
        self.assertEqual(change.author_name, "Luc Martin")

    def test_staff_cancel_without_reason_refused_by_service(self):
        with self.assertRaises(ValueError):
            cancel_by_staff(self.order, self.agent, "")
        self.assertFalse(self.order.history.exists())

    def test_confirming_twice_refused(self):
        confirm_by_staff(self.order, self.agent)

        with self.assertRaises(TransitionNotAllowed):
            confirm_by_staff(self.order, self.agent)
        self.assertEqual(Order.objects.get().history.count(), 1)

    def test_client_cannot_cancel_confirmed_order(self):
        confirm_by_staff(self.order, self.agent)

        with self.assertRaises(TransitionNotAllowed):
            cancel_by_client(self.order)


class PriceAtConfirmationTests(TestCase):
    """Le prix peut varier entre la demande et la confirmation : il est recalculé aux tarifs du jour."""

    def setUp(self):
        self.agent = create_agent()
        self.marie = create_client()
        country = create_country()
        self.destination = create_destination(country, "Kyoto", price_from=Decimal("1000"))
        self.tea = create_activity(country, "Cérémonie du thé", price_per_person=Decimal("50"))
        # 2 adultes : (1000 + 50) × 2
        self.order = create_order(
            self.marie, self.destination, [self.tea], adults=2, estimated_price=Decimal("2100.00")
        )

    def raise_prices(self):
        self.destination.price_from = Decimal("1100")
        self.destination.save()
        self.tea.price_per_person = Decimal("60")
        self.tea.save()

    def test_confirmation_uses_current_rates(self):
        self.raise_prices()

        confirm_by_staff(self.order, self.agent)

        self.order.refresh_from_db()
        self.assertEqual(self.order.confirmed_price, Decimal("2320.00"))  # (1100 + 60) × 2
        self.assertEqual(self.order.estimated_price, Decimal("2100.00"))
        self.assertEqual(self.order.latest_price, Decimal("2320.00"))
        self.assertEqual(
            self.order.history.get().reason, "Prix recalculé aux tarifs du jour : 2100,00 € → 2320,00 €."
        )

    def test_unchanged_price_leaves_no_note(self):
        confirm_by_staff(self.order, self.agent)

        self.order.refresh_from_db()
        self.assertEqual(self.order.confirmed_price, Decimal("2100.00"))
        self.assertEqual(self.order.history.get().reason, "")

    def test_agent_sees_the_price_before_confirming(self):
        self.raise_prices()
        self.client.force_login(self.agent)

        response = self.client.get(reverse("manage_order_detail", args=[self.order.pk]))

        self.assertContains(response, "Prix aux tarifs actuels : <strong>2320,00 €</strong>", html=False)

    def test_client_sees_both_prices(self):
        self.raise_prices()
        confirm_by_staff(self.order, self.agent)
        self.client.force_login(self.marie)

        detail = self.client.get(reverse("my_order_detail", args=[self.order.pk]))
        listing = self.client.get(reverse("my_orders"))

        self.assertContains(detail, "2100,00 €")
        self.assertContains(detail, "Prix à la confirmation")
        self.assertContains(detail, "2320,00 €")
        self.assertContains(listing, "2320,00 €")
        self.assertNotContains(listing, "2100,00 €")

    def test_price_set_after_quote_request_no_longer_shown_on_quote(self):
        lisbon = create_destination(create_country("Portugal"), "Lisbonne")
        order = create_order(self.marie, lisbon, adults=1)
        lisbon.price_from = Decimal("800")
        lisbon.save()
        confirm_by_staff(order, self.agent)
        self.client.force_login(self.marie)

        detail = self.client.get(reverse("my_order_detail", args=[order.pk]))
        listing = self.client.get(reverse("my_orders"))

        self.assertContains(detail, "800,00 €")
        self.assertNotContains(detail, "sur devis")
        self.assertContains(listing, "800,00 €")
        self.assertNotContains(listing, "sur devis")


class DepartureDateTests(TestCase):
    """Décision de la cliente : une demande dont la date de départ est passée ne se confirme plus."""

    def setUp(self):
        self.agent = create_agent()
        self.client.force_login(self.agent)
        self.order = create_order(create_client(), create_destination(create_country()))
        # La demande a été faite à temps, mais personne ne l'a traitée avant le départ.
        Order.objects.filter(pk=self.order.pk).update(
            departure_date=timezone.localdate() - timedelta(days=1),
            return_date=timezone.localdate() + timedelta(days=5),
        )
        self.order.refresh_from_db()

    def test_page_explains_and_offers_cancel_only(self):
        response = self.client.get(reverse("manage_order_detail", args=[self.order.pk]))

        self.assertContains(response, "La date de départ est passée")
        self.assertNotContains(response, reverse("manage_confirm_order", args=[self.order.pk]))
        self.assertContains(response, reverse("manage_cancel_order", args=[self.order.pk]))

    def test_posting_confirm_shows_the_reason(self):
        response = self.client.post(reverse("manage_confirm_order", args=[self.order.pk]), follow=True)

        self.assertContains(response, "ne peut plus être confirmée")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Status.PENDING)

    def test_departure_today_can_still_be_confirmed(self):
        Order.objects.filter(pk=self.order.pk).update(departure_date=timezone.localdate())
        self.order.refresh_from_db()

        confirm_by_staff(self.order, self.agent)

        self.assertEqual(self.order.status, Status.CONFIRMED)
