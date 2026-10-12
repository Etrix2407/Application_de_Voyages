from datetime import datetime, timezone as dt_timezone

from django.test import TestCase

from accounts.models import AccountEmail, DeletedClientAccount, User
from accounts.services.account_deletion import delete_account

from .factories import create_agent, create_client

JOINED = datetime(2025, 3, 14, 9, 30, tzinfo=dt_timezone.utc)


class DeletedClientAccountTests(TestCase):
    # Le cas « avait passé une demande » est vérifié avec le tableau de pilotage (dashboard).

    def test_deleted_client_leaves_anonymous_trace(self):
        delete_account(create_client(date_joined=JOINED))

        trace = DeletedClientAccount.objects.get()
        self.assertEqual(trace.date_joined, JOINED)
        self.assertFalse(trace.had_orders)

    def test_deletion_outside_delete_account_is_traced(self):
        create_client()

        User.objects.all().delete()

        self.assertEqual(DeletedClientAccount.objects.count(), 1)

    def test_unconfirmed_client_and_staff_not_traced(self):
        delete_account(create_client(email_confirmed_at=None), AccountEmail.UNCONFIRMED_ACCOUNT_DELETED)
        delete_account(create_agent(), AccountEmail.STAFF_ACCOUNT_DELETED)

        self.assertFalse(DeletedClientAccount.objects.exists())
