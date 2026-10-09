from datetime import date, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from accounts.models import Role
from accounts.validators import validate_belgian_phone

from .factories import PASSWORD, create_agent, create_client

User = get_user_model()


class UserCreationTests(TestCase):
    def test_client_by_default(self):
        client = create_client()

        self.assertEqual(client.role, Role.CLIENT)
        self.assertTrue(client.is_client)
        self.assertFalse(client.is_staff_member)
        self.assertIsNone(client.employee_number)

    def test_password_hashed(self):
        client = create_client()

        self.assertNotEqual(client.password, PASSWORD)
        self.assertTrue(client.check_password(PASSWORD))

    def test_login_with_email(self):
        create_client()

        self.assertIsNotNone(authenticate(email="client@example.com", password=PASSWORD))

    def test_email_lowercased(self):
        client = create_client(email="  Client@Example.COM ")

        self.assertEqual(client.email, "client@example.com")

    def test_email_unique_case_insensitive(self):
        create_client(email="client@example.com")

        with self.assertRaises(IntegrityError):
            create_agent(email="CLIENT@example.com")

    def test_email_required(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("", PASSWORD)


class EmployeeNumberTests(TestCase):
    def test_numbers_assigned_in_order(self):
        first = create_agent(email="a1@example.com")
        second = create_agent(email="a2@example.com")

        self.assertEqual(first.employee_number, "AG0001")
        self.assertEqual(second.employee_number, "AG0002")

    def test_number_kept_on_update(self):
        agent = create_agent()
        agent.last_name = "Nouveau"
        agent.save()

        agent.refresh_from_db()
        self.assertEqual(agent.employee_number, "AG0001")

    def test_superuser_is_administrator(self):
        manager = User.objects.create_superuser(
            "gerante@example.com", PASSWORD, last_name="Durand", first_name="Anne"
        )

        self.assertEqual(manager.role, Role.ADMINISTRATOR)
        self.assertTrue(manager.is_administrator)
        self.assertTrue(manager.is_staff_member)
        self.assertEqual(manager.employee_number, "AG0001")

    def test_superuser_with_other_role_rejected(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "x@example.com", PASSWORD, last_name="X", first_name="Y", role=Role.AGENT
            )


class ClientValidationTests(TestCase):
    def new_client(self, **fields):
        fields.setdefault("birth_date", date(1950, 1, 1))
        return User(email="c@example.com", last_name="N", first_name="P", **fields)

    def test_valid_client(self):
        client = self.new_client(phone="0470 12 34 56")

        client.full_clean(exclude=["password"])

        self.assertEqual(client.phone, "0470123456")

    def test_phone_optional(self):
        self.new_client().full_clean(exclude=["password"])

    def test_birth_date_required(self):
        client = self.new_client(birth_date=None)

        with self.assertRaises(ValidationError) as error:
            client.full_clean(exclude=["password"])
        self.assertIn("birth_date", error.exception.message_dict)

    def test_future_birth_date_rejected(self):
        client = self.new_client(birth_date=timezone.localdate() + timedelta(days=1))

        with self.assertRaises(ValidationError) as error:
            client.full_clean(exclude=["password"])
        self.assertIn("birth_date", error.exception.message_dict)

    def test_agent_without_birth_date(self):
        agent = User(email="a@example.com", last_name="N", first_name="P", role=Role.AGENT)

        agent.full_clean(exclude=["password"])


class BelgianPhoneTests(SimpleTestCase):
    def test_valid_numbers(self):
        for number in ["0470 12 34 56", "+32 470 12 34 56", "0032470123456", "02/123.45.67"]:
            with self.subTest(number=number):
                validate_belgian_phone(number)

    def test_invalid_numbers(self):
        for number in ["12345", "+33 6 12 34 56 78", "0470 12 34 56 78 9", "abc"]:
            with self.subTest(number=number), self.assertRaises(ValidationError):
                validate_belgian_phone(number)


class PasswordStrengthTests(TestCase):
    def test_strong_password_accepted(self):
        validate_password("soleil-plage-42")

    def test_rejected_passwords(self):
        cases = {
            "trop court": "court12",
            "sans chiffre": "seulementdeslettres",
            "sans lettre": "123456789012",
            "trop courant": "password1234",
        }
        for reason, password in cases.items():
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                validate_password(password)

    def test_password_similar_to_email_rejected(self):
        client = User(email="marie.dupont2024@example.com", last_name="Dupont", first_name="Marie")

        with self.assertRaises(ValidationError):
            validate_password("marie.dupont2024", user=client)


class NormalizationOnSaveTests(TestCase):
    def test_phone_normalized_even_without_full_clean(self):
        client = create_client(phone="0470 12 34 56")

        client.refresh_from_db()
        self.assertEqual(client.phone, "0470123456")
