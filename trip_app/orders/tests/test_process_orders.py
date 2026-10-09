from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
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

    def test_administrator_can_confirm_too(self):
        self.client.force_login(create_admin())

        self.client.post(self.confirm_url)

        self.assertEqual(self.refreshed_status(), Status.CONFIRMED)
        self.assertEqual(self.order.history.get().author_name, "Anne Durand")

    def test_confirmed_order_shows_cancel_only(self):
        confirm_by_staff(self.order, self.agent)

        response = self.client.get(self.detail)

        self.assertNotContains(response, self.confirm_url)
        self.assertContains(response, self.cancel_url)

    def test_staff_cancel_requires_reason(self):
        response = self.client.post(self.cancel_url, {"reason": "   "})

        self.assertContains(response, "Le motif est obligatoire.")
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_staff_cancels_pending_order_with_reason(self):
        response = self.client.post(self.cancel_url, {"reason": "Client injoignable."}, follow=True)

        self.assertContains(response, "est annulée")
        self.assertEqual(self.refreshed_status(), Status.CANCELLED)
        change = self.order.history.get()
        self.assertEqual((change.author_name, change.reason), ("Luc Martin", "Client injoignable."))

    def test_staff_can_cancel_confirmed_order(self):
        confirm_by_staff(self.order, self.agent)

        self.client.post(self.cancel_url, {"reason": "Le client a appelé pour annuler."})

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
        cancel = self.client.post(self.cancel_url, {"reason": "Doublon."}, follow=True)

        self.assertContains(confirm, "Seule une demande en attente peut être confirmée.")
        self.assertContains(cancel, "Cette demande est déjà annulée.")
        self.assertEqual(self.order.history.count(), 1)

    def test_confirm_only_by_post(self):
        self.assertEqual(self.client.get(self.confirm_url).status_code, 405)
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_client_cannot_process_orders(self):
        self.client.force_login(self.marie)

        self.assertEqual(self.client.post(self.confirm_url).status_code, 403)
        self.assertEqual(self.client.post(self.cancel_url, {"reason": "x"}).status_code, 403)
        self.assertEqual(self.refreshed_status(), Status.PENDING)

    def test_client_sees_staff_cancellation_and_reason(self):
        cancel_by_staff(self.order, self.agent, "Destination fermée cette saison.")
        self.client.force_login(self.marie)

        response = self.client.get(reverse("my_order_detail", args=[self.order.pk]))

        self.assertContains(response, "Annulée")
        self.assertContains(response, "Destination fermée cette saison.")
        self.assertContains(response, "Agence")
        self.assertNotContains(response, "Luc Martin")

    def test_client_or_agency_decided_by_who_acted_not_by_name(self):
        # Un agent qui s'appellerait « Client » reste affiché « Agence » au client.
        agent_named_client = StatusChange(author_name="Client", by_client=False)
        client_change = StatusChange(author_name="Client", by_client=True)

        self.assertEqual(agent_named_client.author_for_client, "Agence")
        self.assertEqual(client_change.author_for_client, "Client")

    def test_staff_sees_agent_name_in_history(self):
        cancel_by_staff(self.order, self.agent, "Destination fermée cette saison.")

        self.assertContains(self.client.get(self.detail), "Luc Martin")

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
