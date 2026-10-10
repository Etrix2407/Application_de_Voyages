"""RGPD (portabilité) : fichier « Télécharger mes données ».

Les droits d'accès (visiteur renvoyé vers la connexion) sont vérifiés par la
matrice de test_access.py.
"""

import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import EmailKind, EmailLog
from accounts.tests.factories import create_agent, create_client
from catalog.models import FavoriteDestination
from catalog.tests.factories import create_activity, create_country, create_destination
from orders.tests.factories import create_order
from reviews.tests.factories import create_review, create_trip_done


class DownloadMyDataTests(TestCase):
    def test_file_contains_own_data_only_and_no_password(self):
        marie = create_client(phone="0470123456")
        other = create_client(email="voisin@example.com", last_name="Voisin")
        country = create_country()
        kyoto = create_destination(country, "Kyoto")
        osaka = create_destination(country, "Osaka")
        create_order(marie, kyoto, [create_activity(country, "Cérémonie du thé")], remarks="Chambre calme")
        create_review(create_trip_done(marie, kyoto), title="Séjour inoubliable")
        FavoriteDestination.objects.create(client=marie, destination=kyoto)
        create_order(other, osaka, remarks="Remarque du voisin")
        create_review(create_trip_done(other, osaka), title="Avis du voisin")
        FavoriteDestination.objects.create(client=other, destination=osaka)
        EmailLog.objects.create(
            recipient=marie.email, kind=EmailKind.PASSWORD_RESET, subject="Changement de votre mot de passe", user=marie
        )
        EmailLog.objects.create(
            recipient=other.email, kind=EmailKind.PASSWORD_RESET, subject="Objet du voisin", user=other
        )
        self.client.force_login(marie)

        response = self.client.get(reverse("download_my_data"))

        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode()
        data = json.loads(content)
        self.assertEqual(data["profile"]["email"], "client@example.com")
        self.assertEqual(data["profile"]["phone"], "0470123456")
        self.assertEqual([order["remarks"] for order in data["orders"]], ["", "Chambre calme"])
        self.assertIn("Cérémonie du thé", content)
        self.assertEqual([review["title"] for review in data["reviews"]], ["Séjour inoubliable"])
        self.assertEqual([favorite["name"] for favorite in data["favorites"]["destinations"]], ["Kyoto"])
        self.assertEqual(
            [(email["kind"], email["subject"], email["status"]) for email in data["emails"]],
            [("Mot de passe oublié", "Changement de votre mot de passe", "En attente")],
        )
        for other_data in ("voisin@example.com", "Remarque du voisin", "Avis du voisin", "Osaka", "Objet du voisin"):
            self.assertNotIn(other_data, content)
        self.assertNotIn("password", content)
        self.assertNotIn(marie.password, content)

    def test_staff_member_gets_own_profile_only(self):
        agent = create_agent()
        create_client()
        self.client.force_login(agent)

        data = self.client.get(reverse("download_my_data")).json()

        self.assertEqual(list(data), ["profile", "emails"])
        self.assertEqual(data["profile"]["email"], "agent@example.com")
        self.assertEqual(data["profile"]["employee_number"], "AG0001")
