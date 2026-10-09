from django.contrib.auth.hashers import PBKDF2PasswordHasher, check_password, make_password
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.hashers import PepperedPBKDF2PasswordHasher

from .factories import PASSWORD, create_client


# Mêmes algorithmes avec peu d'itérations, pour garder des tests rapides.
class FastPepperedHasher(PepperedPBKDF2PasswordHasher):
    iterations = 1000


class FastPBKDF2Hasher(PBKDF2PasswordHasher):
    iterations = 1000


PEPPERED = "accounts.tests.test_hashers.FastPepperedHasher"
WITHOUT_PEPPER = "accounts.tests.test_hashers.FastPBKDF2Hasher"


@override_settings(PASSWORD_HASHERS=[PEPPERED, WITHOUT_PEPPER], PASSWORD_PEPPER="poivre-secret")
class PepperTests(TestCase):
    def test_password_hashed_with_pepper_and_salt(self):
        first, second = make_password(PASSWORD), make_password(PASSWORD)

        self.assertTrue(first.startswith("pbkdf2_sha256_pepper$"))
        self.assertNotEqual(first, second)  # sel aléatoire propre à chaque mot de passe
        self.assertTrue(check_password(PASSWORD, first))
        self.assertFalse(check_password("autre-mot-2026", first))

    def test_stolen_database_without_pepper_is_useless(self):
        encoded = make_password(PASSWORD)

        with self.settings(PASSWORD_PEPPER="mauvais-poivre"):
            self.assertFalse(check_password(PASSWORD, encoded))

    def test_peppered_hash_differs_from_plain_hash_with_same_salt(self):
        peppered = FastPepperedHasher().encode(PASSWORD, "selfixe")
        plain = FastPBKDF2Hasher().encode(PASSWORD, "selfixe")

        self.assertNotEqual(peppered.split("$")[-1], plain.split("$")[-1])

    def test_old_password_without_pepper_upgraded_at_login(self):
        user = create_client()
        user.password = FastPBKDF2Hasher().encode(PASSWORD, "ancienSel")
        user.save(update_fields=["password"])

        response = self.client.post(reverse("login"), {"username": user.email, "password": PASSWORD})

        self.assertRedirects(response, reverse("home"))
        user.refresh_from_db()
        self.assertTrue(user.password.startswith("pbkdf2_sha256_pepper$"))
        self.assertTrue(user.check_password(PASSWORD))


@override_settings(PASSWORD_HASHERS=[WITHOUT_PEPPER], PASSWORD_PEPPER="")
class MissingPepperTests(TestCase):
    def test_peppered_password_refused_cleanly_when_pepper_not_configured(self):
        with self.settings(PASSWORD_HASHERS=[PEPPERED], PASSWORD_PEPPER="poivre-secret"):
            encoded = make_password(PASSWORD)

        # Sans le poivre, la vérification échoue proprement (pas de contournement ni de plantage).
        self.assertFalse(check_password(PASSWORD, encoded))
