import re
from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import create_admin, create_client
from catalog.tests.factories import create_country, create_destination
from dashboard.models import ExportLog
from dashboard.services.periods import DateBasis, Shortcut
from orders.models import OrderStatus
from orders.tests.factories import create_order

# L'accès (administrateur seulement, en GET comme en POST) est vérifié par la matrice d'accès
# (config/test_access.py).

OCTOBER = {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.ORDERED, "start": "2026-10-01", "end": "2026-10-31"}


def in_october(day: int, hour: int = 10) -> datetime:
    return timezone.make_aware(datetime(2026, 10, day, hour))


class OrderExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_admin()
        cls.client_user = create_client()
        cls.destination = create_destination(create_country())
        cls.order = create_order(
            cls.client_user,
            cls.destination,
            created_at=in_october(5),
            departure_date=date(2026, 12, 20),
            adults=2,
            children=1,
            estimated_price=Decimal("1500.00"),
            discount=Decimal("100.00"),
            confirmed_price=Decimal("1620.50"),
            confirmed_discount=Decimal("120.00"),
            status=OrderStatus.CONFIRMED,
            remarks="Allergie aux arachides",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def export(self, data=OCTOBER):
        return self.client.post(reverse("export_orders"), data)

    def lines(self, response) -> list[str]:
        content = response.content.decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        return content.removeprefix("﻿").splitlines()

    def test_exports_one_line_per_order_in_belgian_format(self):
        response = self.export()

        self.assertEqual(response["Content-Disposition"], 'attachment; filename="commandes_2026-10-01_2026-10-31.csv"')
        header, row = self.lines(response)
        self.assertTrue(header.startswith("Numéro;Date de commande;Date de départ;Destination;Pays;"))
        # Montant et remise de la confirmation, voyageurs = adultes + enfants, état en français.
        self.assertEqual(
            row, f"{self.order.pk};05/10/2026;20/12/2026;Kyoto;Japon;{self.client_user.pk};3;1620,50;120,00;Confirmée"
        )

    def test_no_name_email_or_remarks(self):
        content = self.export().content.decode("utf-8")

        for personal in ("Dupont", "Marie", self.client_user.email, "Allergie"):
            self.assertNotIn(personal, content)

    def test_deleted_client_has_empty_number(self):
        anonymized = create_order(None, self.destination, created_at=in_october(6))

        rows = self.lines(self.export())[1:]

        self.assertTrue(rows[1].startswith(f"{anonymized.pk};06/10/2026;"))
        self.assertEqual(rows[1].split(";")[5], "")

    def test_formula_cells_are_neutralised(self):
        create_order(None, self.destination, created_at=in_october(6), destination_name="=HYPERLINK(\"x\")")
        create_order(None, self.destination, created_at=in_october(7), country_name="@SUM(A1)")

        content = self.export().content.decode("utf-8")

        self.assertIn(";\"'=HYPERLINK(\"\"x\"\")\";", content)
        self.assertIn(";'@SUM(A1);", content)

    def test_export_is_logged_with_its_period(self):
        create_order(None, self.destination, created_at=in_october(1, hour=0))  # 0 h à Bruxelles : compte.
        create_order(None, self.destination, created_at=timezone.make_aware(datetime(2026, 11, 1, 0, 30)))

        self.export()

        log = ExportLog.objects.get()
        self.assertEqual(
            (log.author, log.author_name, log.start, log.end, log.basis, log.row_count),
            (self.admin, "Anne Durand", date(2026, 10, 1), date(2026, 10, 31), DateBasis.ORDERED, 2),
        )

    def test_pilotage_page_sends_the_displayed_period(self):
        page = self.client.get(reverse("pilotage_dashboard"), {**OCTOBER, "basis": DateBasis.DEPARTURE})

        hidden = dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)"', page.content.decode()))
        hidden.pop("csrfmiddlewaretoken")
        self.assertEqual(
            hidden,
            {"shortcut": Shortcut.CUSTOM, "basis": DateBasis.DEPARTURE, "start": "2026-10-01", "end": "2026-10-31"},
        )

    def test_invalid_period_redirects_without_log(self):
        response = self.export({**OCTOBER, "end": ""})

        self.assertRedirects(response, reverse("pilotage_dashboard"), fetch_redirect_response=False)
        self.assertFalse(ExportLog.objects.exists())

    def test_get_is_refused(self):
        self.assertEqual(self.client.get(reverse("export_orders")).status_code, 405)
