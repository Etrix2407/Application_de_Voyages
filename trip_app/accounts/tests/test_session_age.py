from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.signals import STAFF_SESSION_AGE

from .factories import PASSWORD, create_admin, create_agent, create_client


class SessionAgeTests(TestCase):
    """Le personnel est déconnecté après une journée de travail ; les clients restent connectés."""

    def setUp(self):
        cache.clear()

    def log_in(self, user):
        self.client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
        return self.client.session.get_expiry_age()

    def test_staff_session_lasts_one_working_day(self):
        for user in [create_agent(), create_admin()]:
            with self.subTest(role=user.role):
                # Échéance fixe 8 h après la connexion : quelques secondes ont passé depuis.
                self.assertAlmostEqual(self.log_in(user), STAFF_SESSION_AGE.total_seconds(), delta=5)
                self.client.logout()

    def test_client_session_keeps_default_duration(self):
        self.assertEqual(self.log_in(create_client()), settings.SESSION_COOKIE_AGE)
