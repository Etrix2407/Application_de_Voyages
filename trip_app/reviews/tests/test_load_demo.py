from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from catalog.models import Activity, Destination, Country

User = get_user_model()


def load_demo() -> str:
    output = StringIO()
    call_command("load_demo", stdout=output)
    return output.getvalue()


@override_settings(DEBUG=True)
class LoadDemoTests(TestCase):
    def test_fictional_data_marked_as_example(self):
        load_demo()

        self.assertEqual(Country.objects.count(), 3)
        for items in [Country.objects.all(), Destination.objects.all(), Activity.objects.all()]:
            for item in items:
                with self.subTest(item=item.name):
                    self.assertTrue(item.name.startswith("Exemple — "))

    def test_one_inactive_country_for_demo(self):
        load_demo()

        self.assertEqual(Country.objects.visible().count(), 2)

    def test_demo_accounts_with_random_password(self):
        output = load_demo()

        client = User.objects.get(email="client.demo@example.com")
        password = output.split("client.demo@example.com / mot de passe : ")[1].split()[0]
        self.assertTrue(client.check_password(password))
        self.assertTrue(client.is_client)
        self.assertTrue(User.objects.get(email="agent.demo@example.com").is_staff_member)

    def test_rerun_creates_no_duplicate(self):
        load_demo()
        output = load_demo()

        self.assertEqual(Country.objects.count(), 3)
        self.assertEqual(User.objects.count(), 2)
        self.assertIn("Déjà présent", output)

    @override_settings(DEBUG=False)
    def test_refused_outside_development(self):
        with self.assertRaises(CommandError):
            load_demo()
        self.assertFalse(Country.objects.exists())
