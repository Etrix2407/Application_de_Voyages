from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

BEFORE_INTERNAL_REASON = [("orders", "0011_merge_20261010_1736")]
INTERNAL_REASON_ADDED = [("orders", "0012_status_change_internal_reason")]
ACCOUNT_DELETED_MOVED = [("orders", "0013_account_deleted_reason_internal")]
ACCOUNT_DELETED_REASON = "Compte client supprimé : demande annulée automatiquement."


class StatusChangeReasonMigrationTests(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self.migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())

    def create_cancellation(self, apps, reason):
        country = apps.get_model("catalog", "Country").objects.create(name="Japon")
        destination = apps.get_model("catalog", "Destination").objects.create(country=country, name="Kyoto")
        order = apps.get_model("orders", "Order").objects.create(
            destination=destination,
            destination_name="Kyoto",
            country_name="Japon",
            departure_date=date(2027, 3, 1),
            return_date=date(2027, 3, 10),
            adults=2,
            estimated_price=0,
            status="cancelled",
        )
        apps.get_model("orders", "StatusChange").objects.create(
            order=order, status="cancelled", author_name="Client", reason=reason
        )

    def reasons(self, apps):
        return apps.get_model("orders", "StatusChange").objects.values_list("reason", "internal_reason").get()

    def test_existing_staff_reason_becomes_client_explanation(self):
        self.create_cancellation(self.migrate(BEFORE_INTERNAL_REASON), "Destination fermée cette saison.")

        apps = self.migrate(ACCOUNT_DELETED_MOVED)

        self.assertEqual(self.reasons(apps), ("Destination fermée cette saison.", ""))

    def test_account_deleted_reason_moved_to_internal_and_back(self):
        self.create_cancellation(self.migrate(INTERNAL_REASON_ADDED), ACCOUNT_DELETED_REASON)

        apps = self.migrate(ACCOUNT_DELETED_MOVED)
        self.assertEqual(self.reasons(apps), ("", ACCOUNT_DELETED_REASON))

        apps = self.migrate(INTERNAL_REASON_ADDED)
        self.assertEqual(self.reasons(apps), (ACCOUNT_DELETED_REASON, ""))
