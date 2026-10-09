from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from accounts.services.throttling import (
    get_client_ip,
    login_failures_by_ip,
    password_reset_requests_by_ip,
    sign_ups_by_ip,
)

from .factories import PASSWORD, create_client

OFFICE_IP = "203.0.113.10"
OTHER_IP = "198.51.100.20"


@override_settings(NUM_PROXIES=0)
class ClientIpTests(SimpleTestCase):
    def request(self, **meta):
        return RequestFactory().get("/", REMOTE_ADDR=OFFICE_IP, **meta)

    def test_connection_ip_by_default(self):
        self.assertEqual(get_client_ip(self.request()), OFFICE_IP)

    def test_forwarded_header_ignored_without_trusted_proxy(self):
        # Un attaquant ne doit pas pouvoir choisir son IP en forgeant l'en-tête.
        request = self.request(HTTP_X_FORWARDED_FOR="1.2.3.4")

        self.assertEqual(get_client_ip(request), OFFICE_IP)

    @override_settings(NUM_PROXIES=1)
    def test_ip_added_by_trusted_proxy(self):
        request = self.request(HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7")

        self.assertEqual(get_client_ip(request), "198.51.100.7")


class LoginIpLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def log_in(self, email, password="mauvais-mdp-0", ip=OFFICE_IP):
        return self.client.post(
            reverse("login"), {"username": email, "password": password}, REMOTE_ADDR=ip
        )

    def spray(self):
        """Un essai raté sur de nombreux comptes différents depuis la même IP."""
        for i in range(login_failures_by_ip.max_attempts):
            self.log_in(f"cible{i}@example.com")

    def test_password_spraying_blocked_by_ip(self):
        create_client()
        self.spray()

        response = self.log_in("client@example.com", PASSWORD)

        self.assertContains(response, "Trop de tentatives")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_other_ip_not_affected(self):
        create_client()
        self.spray()

        self.assertRedirects(self.log_in("client@example.com", PASSWORD, ip=OTHER_IP), reverse("home"))

    def test_successful_login_does_not_reset_ip_counter(self):
        create_client()
        for i in range(login_failures_by_ip.max_attempts - 1):
            self.log_in(f"cible{i}@example.com")
        self.log_in("client@example.com", PASSWORD)
        self.client.logout()

        self.log_in("encore@example.com")

        self.assertTrue(login_failures_by_ip.is_locked(OFFICE_IP))


class SignUpIpLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def sign_up(self, number, ip=OFFICE_IP):
        data = {
            "first_name": "Marie",
            "last_name": "Dupont",
            "email": f"nouveau{number}@example.com",
            "birth_date": "1955-04-12",
            "password1": "soleil-plage-42",
            "password2": "soleil-plage-42",
            "consent": "on",
        }
        response = self.client.post(reverse("sign_up"), data, REMOTE_ADDR=ip)
        self.client.logout()
        return response

    def test_mass_sign_up_blocked_by_ip(self):
        for number in range(sign_ups_by_ip.max_attempts):
            self.sign_up(number)

        response = self.sign_up(99)

        self.assertContains(response, "Trop d&#x27;inscriptions")
        self.assertEqual(User.objects.count(), sign_ups_by_ip.max_attempts)

    def test_other_ip_can_still_sign_up(self):
        for number in range(sign_ups_by_ip.max_attempts):
            self.sign_up(number)

        self.assertEqual(self.sign_up(99, ip=OTHER_IP).status_code, 302)


class PasswordResetIpLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_links_to_many_addresses_blocked_by_ip(self):
        limit = password_reset_requests_by_ip.max_attempts
        for number in range(limit + 3):
            create_client(email=f"cible{number}@example.com")

        for number in range(limit + 3):
            response = self.client.post(
                reverse("password_reset"), {"email": f"cible{number}@example.com"}, REMOTE_ADDR=OFFICE_IP
            )
            # La page reste identique : la limite n'est pas révélée.
            self.assertRedirects(response, reverse("password_reset_done"))

        self.assertEqual(len(mail.outbox), limit)
