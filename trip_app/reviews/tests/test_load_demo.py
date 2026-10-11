from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from catalog.models import Country
from orders.models import Order
from promotions.models import Promotion
from reviews.models import Review

User = get_user_model()


def load_demo() -> str:
    output = StringIO()
    call_command("load_demo", stdout=output)
    return output.getvalue()


@override_settings(DEBUG=True)
class LoadDemoTests(TestCase):
    def test_rerun_creates_no_duplicate(self):
        load_demo()
        output = load_demo()

        self.assertEqual(Country.objects.count(), 3)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(Promotion.objects.count(), 2)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(Review.objects.count(), 1)
        self.assertIn("Déjà présent", output)

    @override_settings(DEBUG=False)
    def test_refused_outside_development(self):
        with self.assertRaises(CommandError):
            load_demo()
        self.assertFalse(Country.objects.exists())

    def test_refused_on_database_with_real_accounts(self):
        User.objects.create_superuser("gerante@agence.be", "mot-de-passe-123", last_name="G", first_name="G")

        with self.assertRaisesMessage(CommandError, "comptes réels"):
            load_demo()
        self.assertFalse(Country.objects.exists())
        self.assertFalse(Promotion.objects.exists())
