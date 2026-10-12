from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailFailure, EmailLog, EmailStatus
from accounts.services.account_deletion import delete_account
from accounts.services.address_check import ADDRESS_CHECK_FAILURES
from accounts.services.emails import MAX_ATTEMPTS
from accounts.tests.factories import create_admin, create_client
from catalog.tests.factories import create_country, create_destination
from dashboard.services.clients import client_figures
from dashboard.services.emails import email_figures
from dashboard.services.periods import custom_period
from orders.tests.factories import create_order

BRUSSELS = ZoneInfo("Europe/Brussels")
MARCH = custom_period(date(2026, 3, 1), date(2026, 3, 31))


def joined(day: int) -> datetime:
    """Midi à Bruxelles, un jour de mars 2026."""
    return datetime(2026, 3, day, 12, tzinfo=BRUSSELS)


class ClientFiguresTests(TestCase):
    def setUp(self):
        self.destination = create_destination(create_country())

    def test_created_accounts_unchanged_after_deletion(self):
        create_client("a@example.com", date_joined=joined(31))
        leaving = create_client("b@example.com", date_joined=joined(10))
        create_client("fevrier@example.com", date_joined=datetime(2026, 2, 10, tzinfo=BRUSSELS))
        # 1er avril à 0 h 30 à Bruxelles : encore le 31 mars en UTC, mais compte pour avril.
        create_client("avril@example.com", date_joined=datetime(2026, 4, 1, 0, 30, tzinfo=BRUSSELS))
        before = client_figures(MARCH)

        delete_account(leaving)
        after = client_figures(MARCH)

        self.assertEqual(before.created, 2)
        self.assertEqual(after.created, 2)
        self.assertEqual(after.created_comparison.text, "+100 %")

    def test_registered_clients_only_active_and_confirmed(self):
        buyer = create_client("a@example.com")
        create_order(buyer, self.destination)
        create_client("b@example.com")
        create_client("inactif@example.com", is_active=False)
        create_client("non-confirme@example.com", email_confirmed_at=None)
        create_admin()
        delete_account(create_client("supprime@example.com"))

        figures = client_figures(MARCH)

        self.assertEqual(figures.registered, 2)
        self.assertEqual(figures.registered_with_orders, 1)

    def test_conversion_keeps_deleted_client_who_ordered(self):
        leaving = create_client("a@example.com", date_joined=joined(5))
        create_order(leaving, self.destination)
        create_client("b@example.com", date_joined=joined(6))
        create_client("c@example.com", date_joined=joined(7))
        create_client("non-confirme@example.com", date_joined=joined(8), email_confirmed_at=None)

        delete_account(leaving)

        self.assertEqual(client_figures(MARCH).conversion_rate, "33 %")

    def test_no_account_created_shows_dash(self):
        self.assertEqual(client_figures(MARCH).conversion_rate, "—")


class EmailFiguresTests(TestCase):
    def test_failures_of_last_seven_days(self):
        now = timezone.now()
        for days_ago, status in (
            (timedelta(days=7) - timedelta(minutes=1), EmailStatus.FAILED),
            (timedelta(days=7) + timedelta(minutes=1), EmailStatus.FAILED),
            (timedelta(hours=1), EmailStatus.SENT),
        ):
            EmailLog.objects.create(kind="test", subject="Test", status=status, last_attempt_at=now - days_ago)

        self.assertEqual(email_figures(now).recent_failures, 1)

    def test_clients_with_address_to_check(self):
        client = create_client()
        create_client("autre@example.com")
        for _ in range(ADDRESS_CHECK_FAILURES):
            EmailLog.objects.create(
                kind="test",
                subject="Test",
                recipient=client.email,
                user=client,
                status=EmailStatus.FAILED,
                failure=EmailFailure.RECIPIENT_REFUSED,
                attempts=MAX_ATTEMPTS,
                last_attempt_at=timezone.now(),
            )

        self.assertEqual(email_figures().addresses_to_check, 1)

    def test_failures_link_to_journal(self):
        cache.clear()
        self.client.force_login(create_admin())

        response = self.client.get(reverse("pilotage_dashboard"))

        self.assertContains(response, "E-mails en échec sur les 7 derniers jours")
        self.assertContains(response, f'href="{reverse("email_failure_list")}"')
