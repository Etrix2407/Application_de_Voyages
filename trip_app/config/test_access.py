"""Matrice d'accès : chaque route du site déclare qui peut l'ouvrir.

Le test échoue si une route est ajoutée sans être déclarée ici : ainsi, aucune
page ne peut être publiée par oubli sans contrôle d'accès.
"""

from django.conf import settings
from django.test import TestCase
from django.urls import URLResolver, get_resolver, reverse

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.tests.factories import create_order
from promotions.tests.factories import create_promotion
from reviews.tests.factories import create_review, create_trip_done

PUBLIC, LOGGED_IN, CLIENT, STAFF, ADMIN = "public", "connecté", "client", "personnel", "administrateur"

ACCESS = {
    "home": PUBLIC,
    "privacy": PUBLIC,
    "sign_up": PUBLIC,
    "sign_up_done": PUBLIC,
    "confirm_sign_up": PUBLIC,
    "resend_confirmation": PUBLIC,
    "confirm_email_change": PUBLIC,
    "login": PUBLIC,
    "logout": PUBLIC,
    "password_reset": PUBLIC,
    "password_reset_done": PUBLIC,
    "password_reset_confirm": PUBLIC,
    "password_reset_complete": PUBLIC,
    "country_list": PUBLIC,
    "profile": LOGGED_IN,
    "change_password": LOGGED_IN,
    "search": PUBLIC,
    "destination_list": PUBLIC,
    "country_detail": PUBLIC,
    "destination_detail": PUBLIC,
    "activity_detail": PUBLIC,
    "edit_profile": CLIENT,
    "change_email": CLIENT,
    "delete_account": CLIENT,
    "favorite_list": CLIENT,
    "add_favorite": CLIENT,
    "remove_favorite": CLIENT,
    "create_order": CLIENT,
    "my_orders": CLIENT,
    "my_order_detail": CLIENT,
    "cancel_my_order": CLIENT,
    "my_reviews": CLIENT,
    "create_review": CLIENT,
    "edit_review": CLIENT,
    "remove_review": CLIENT,
    "manage_pending_reviews": STAFF,
    "manage_reviews": STAFF,
    "manage_review_detail": STAFF,
    "manage_publish_review": STAFF,
    "manage_refuse_review": STAFF,
    "manage_respond_review": STAFF,
    "manage_orders": STAFF,
    "manage_order_detail": STAFF,
    "manage_confirm_order": STAFF,
    "manage_cancel_order": STAFF,
    "client_list": STAFF,
    "edit_client": STAFF,
    "send_client_link": STAFF,
    "manage_country_list": STAFF,
    "manage_create_country": STAFF,
    "manage_country": STAFF,
    "manage_edit_country": STAFF,
    "manage_delete_country": STAFF,
    "manage_create_destination": STAFF,
    "manage_edit_destination": STAFF,
    "manage_delete_destination": STAFF,
    "manage_create_activity": STAFF,
    "manage_edit_activity": STAFF,
    "manage_delete_activity": STAFF,
    "manage_promotions": STAFF,
    "manage_promotion_detail": STAFF,
    "manage_create_promotion": ADMIN,
    "manage_edit_promotion": ADMIN,
    "manage_disable_promotion": ADMIN,
    "manage_delete_promotion": ADMIN,
    "staff_list": ADMIN,
    "create_agent": ADMIN,
    "edit_staff_member": ADMIN,
    "deactivate_staff_member": ADMIN,
    "reactivate_staff_member": ADMIN,
    "resend_staff_link": ADMIN,
    "delete_staff_member": ADMIN,
}

# Rôles autorisés pour chaque niveau d'accès.
ALLOWED = {
    PUBLIC: {"visiteur", "client", "agent", "administrateur"},
    LOGGED_IN: {"client", "agent", "administrateur"},
    CLIENT: {"client"},
    STAFF: {"agent", "administrateur"},
    ADMIN: {"administrateur"},
}


def named_routes(patterns=None):
    for pattern in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(pattern, URLResolver):
            yield from named_routes(pattern.url_patterns)
        elif pattern.name:
            yield pattern.name


class AccessMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client_user = create_client()
        cls.agent = create_agent()
        cls.admin = create_admin()
        cls.other_agent = create_agent(email="autre.agent@example.com")
        country = create_country()
        cls.destination = create_destination(country)
        cls.activity = create_activity(country, destination=cls.destination)
        cls.country = country
        cls.order = create_order(cls.client_user, cls.destination)
        cls.trip_to_review = create_trip_done(cls.client_user, cls.destination)
        cls.review = create_review(create_trip_done(cls.client_user, cls.destination))
        cls.promotion = create_promotion()

    def url_kwargs(self, name):
        member = self.other_agent.pk
        return {
            "edit_client": {"pk": self.client_user.pk},
            "send_client_link": {"pk": self.client_user.pk},
            "edit_staff_member": {"pk": member},
            "deactivate_staff_member": {"pk": member},
            "reactivate_staff_member": {"pk": member},
            "resend_staff_link": {"pk": member},
            "delete_staff_member": {"pk": member},
            "country_detail": {"pk": self.country.pk},
            "destination_detail": {"pk": self.destination.pk},
            "activity_detail": {"pk": self.activity.pk},
            "add_favorite": {"item_type": "activite", "pk": self.activity.pk},
            "remove_favorite": {"item_type": "activite", "pk": self.activity.pk},
            "manage_country": {"pk": self.country.pk},
            "manage_edit_country": {"pk": self.country.pk},
            "manage_delete_country": {"pk": self.country.pk},
            "manage_create_destination": {"country_pk": self.country.pk},
            "manage_edit_destination": {"pk": self.destination.pk},
            "manage_delete_destination": {"pk": self.destination.pk},
            "manage_create_activity": {"country_pk": self.country.pk},
            "manage_edit_activity": {"pk": self.activity.pk},
            "manage_delete_activity": {"pk": self.activity.pk},
            "password_reset_confirm": {"uidb64": "MQ", "token": "jeton-invalide"},
            "confirm_sign_up": {"token": "jeton-invalide"},
            "confirm_email_change": {"token": "jeton-invalide"},
            "create_order": {"destination_pk": self.destination.pk},
            "my_order_detail": {"pk": self.order.pk},
            "cancel_my_order": {"pk": self.order.pk},
            "manage_order_detail": {"pk": self.order.pk},
            "manage_confirm_order": {"pk": self.order.pk},
            "manage_cancel_order": {"pk": self.order.pk},
            "create_review": {"order_pk": self.trip_to_review.pk},
            "edit_review": {"pk": self.review.pk},
            "remove_review": {"pk": self.review.pk},
            "manage_review_detail": {"pk": self.review.pk},
            "manage_publish_review": {"pk": self.review.pk},
            "manage_refuse_review": {"pk": self.review.pk},
            "manage_respond_review": {"pk": self.review.pk},
            "manage_promotion_detail": {"pk": self.promotion.pk},
            "manage_edit_promotion": {"pk": self.promotion.pk},
            "manage_disable_promotion": {"pk": self.promotion.pk},
            "manage_delete_promotion": {"pk": self.promotion.pk},
        }.get(name, {})

    def test_every_route_declares_its_access(self):
        undeclared = set(named_routes()) - set(ACCESS)

        self.assertEqual(undeclared, set(), "Routes sans niveau d'accès déclaré dans ACCESS")

    def test_access_matches_declaration(self):
        users = {
            "visiteur": None,
            "client": self.client_user,
            "agent": self.agent,
            "administrateur": self.admin,
        }
        login_url = reverse(settings.LOGIN_URL)
        for name, level in ACCESS.items():
            url = reverse(name, kwargs=self.url_kwargs(name))
            for role, user in users.items():
                with self.subTest(route=name, role=role):
                    self.client.logout()
                    if user:
                        self.client.force_login(user)

                    # GET uniquement : aucune page ne doit modifier des données en GET.
                    response = self.client.get(url)

                    redirected_to_login = response.status_code == 302 and response["Location"].startswith(login_url)
                    denied = response.status_code in (403, 404) or redirected_to_login
                    if role in ALLOWED[level]:
                        self.assertFalse(denied, f"{role} devrait accéder à {url} ({response.status_code})")
                    elif user is None:
                        self.assertTrue(
                            redirected_to_login, f"un visiteur devrait être renvoyé vers la connexion ({url})"
                        )
                    else:
                        self.assertEqual(response.status_code, 403, f"{role} ne devrait pas accéder à {url}")
