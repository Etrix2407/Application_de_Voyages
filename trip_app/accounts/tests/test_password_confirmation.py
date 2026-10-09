from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.services.throttling import password_confirmations

from .factories import PASSWORD, create_client

WRONG = "mauvais-mot-de-passe-1"


class PasswordReentryLimitTests(TestCase):
    """Le mot de passe redemandé sur une session ouverte ne peut pas être deviné sans limite."""

    def setUp(self):
        cache.clear()
        self.user = create_client()
        self.client.force_login(self.user)
        # Les compteurs ne doivent pas déborder sur les autres tests (même numéro de compte).
        self.addCleanup(cache.clear)

    def forms(self):
        """Pour chaque page : (url, données avec un mot de passe donné)."""
        return {
            "changement d'e-mail": (
                reverse("change_email"),
                lambda password: {"new_email": "nouvelle@example.com", "password": password},
            ),
            "changement de mot de passe": (
                reverse("change_password"),
                lambda password: {
                    "old_password": password,
                    "new_password1": "soleil-plage-42",
                    "new_password2": "soleil-plage-42",
                },
            ),
            "suppression du compte": (reverse("delete_account"), lambda password: {"password": password}),
        }

    def test_locked_after_too_many_wrong_passwords(self):
        for name, (url, data) in self.forms().items():
            with self.subTest(page=name):
                cache.clear()
                for _ in range(password_confirmations.max_attempts):
                    self.assertContains(self.client.post(url, data(WRONG)), "Mot de passe incorrect.")

                # Même le bon mot de passe est refusé pendant le blocage.
                response = self.client.post(url, data(PASSWORD))

                self.assertContains(response, "Trop d&#x27;essais")
                self.assertTrue(User.objects.filter(pk=self.user.pk, email="client@example.com").exists())

    def test_attempts_shared_between_pages(self):
        url, data = self.forms()["suppression du compte"]
        email_url, email_data = self.forms()["changement d'e-mail"]
        for _ in range(password_confirmations.max_attempts):
            self.client.post(email_url, email_data(WRONG))

        self.client.post(url, data(PASSWORD))

        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_resets_counter(self):
        url, data = self.forms()["changement d'e-mail"]
        for _ in range(password_confirmations.max_attempts - 1):
            self.client.post(url, data(WRONG))
        self.client.post(url, data(PASSWORD))

        self.assertContains(self.client.post(url, data(WRONG)), "Mot de passe incorrect.")

    def test_other_accounts_not_affected(self):
        url, data = self.forms()["suppression du compte"]
        for _ in range(password_confirmations.max_attempts):
            self.client.post(url, data(WRONG))
        other = create_client(email="paul@example.com")
        self.client.force_login(other)

        self.client.post(url, data(PASSWORD))

        self.assertFalse(User.objects.filter(pk=other.pk).exists())
