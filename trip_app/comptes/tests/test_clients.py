import re
from datetime import date

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from comptes.models import Role
from comptes.views_clients import CLIENTS_PAR_PAGE

from .fabriques import MOT_DE_PASSE, creer_admin, creer_agent, creer_client


class AccesClientsTests(TestCase):
    def test_client_refuse(self):
        client = creer_client()
        self.client.force_login(creer_client("autre@example.com"))

        self.assertEqual(self.client.get(reverse("liste_clients")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("modifier_client", args=[client.pk])).status_code, 403
        )

    def test_visiteur_redirige(self):
        url = reverse("liste_clients")

        self.assertRedirects(self.client.get(url), f"{reverse('connexion')}?next={url}")

    def test_agent_et_administrateur_autorises(self):
        for utilisateur in [creer_agent(), creer_admin()]:
            self.client.force_login(utilisateur)
            with self.subTest(role=utilisateur.role):
                self.assertEqual(self.client.get(reverse("liste_clients")).status_code, 200)

    def test_comptes_du_personnel_inaccessibles(self):
        agent = creer_agent()
        self.client.force_login(agent)

        self.assertEqual(
            self.client.get(reverse("modifier_client", args=[agent.pk])).status_code, 404
        )


class ListeClientsTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_agent())

    def test_liste_les_clients_sans_le_personnel(self):
        creer_client()

        reponse = self.client.get(reverse("liste_clients"))

        self.assertContains(reponse, "client@example.com")
        self.assertNotContains(reponse, "agent@example.com</td>")

    def test_recherche_sans_accents(self):
        creer_client("helene@example.com", nom="Lefèvre", prenom="Hélène")
        creer_client("paul@example.com", nom="Durand", prenom="Paul")

        reponse = self.client.get(reverse("liste_clients"), {"q": "helene LEFEVRE"})

        self.assertContains(reponse, "helene@example.com")
        self.assertNotContains(reponse, "paul@example.com")

    def test_recherche_par_email(self):
        creer_client("helene@example.com")

        reponse = self.client.get(reverse("liste_clients"), {"q": "HELENE@"})

        self.assertContains(reponse, "helene@example.com")

    def test_pagination(self):
        for i in range(CLIENTS_PAR_PAGE + 1):
            creer_client(f"client{i:02d}@example.com", nom=f"Nom{i:02d}")

        page_1 = self.client.get(reverse("liste_clients"))
        page_2 = self.client.get(reverse("liste_clients"), {"page": 2})

        self.assertEqual(len(page_1.context["page"].object_list), CLIENTS_PAR_PAGE)
        self.assertContains(page_1, "Page suivante")
        self.assertEqual(len(page_2.context["page"].object_list), 1)
        self.assertContains(page_2, "Page précédente")

    def test_page_invalide_affiche_la_derniere(self):
        creer_client()

        reponse = self.client.get(reverse("liste_clients"), {"page": "999"})

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "client@example.com")


class CorrectionClientTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_agent())
        self.client_marie = creer_client()
        self.url = reverse("modifier_client", args=[self.client_marie.pk])

    def test_corriger_les_informations(self):
        reponse = self.client.post(
            self.url,
            {
                "prenom": "Marie-Claire",
                "nom": "Dupont",
                "telephone": "0470 12 34 56",
                "date_naissance": "1955-04-21",
            },
        )

        self.assertRedirects(reponse, reverse("liste_clients"))
        self.client_marie.refresh_from_db()
        self.assertEqual(self.client_marie.prenom, "Marie-Claire")
        self.assertEqual(self.client_marie.telephone, "0470123456")
        self.assertEqual(self.client_marie.date_naissance, date(1955, 4, 21))

    def test_email_et_mot_de_passe_non_modifiables(self):
        self.client.post(
            self.url,
            {
                "prenom": "Marie",
                "nom": "Dupont",
                "date_naissance": "1955-04-12",
                "email": "pirate@example.com",
                "password": "nouveau-mdp-2026",
                "role": Role.ADMINISTRATEUR,
            },
        )

        self.client_marie.refresh_from_db()
        self.assertEqual(self.client_marie.email, "client@example.com")
        self.assertTrue(self.client_marie.check_password(MOT_DE_PASSE))
        self.assertEqual(self.client_marie.role, Role.CLIENT)

    def test_formulaire_sans_champ_email_ni_mot_de_passe(self):
        champs = self.client.get(self.url).context["form"].fields

        self.assertNotIn("email", champs)
        self.assertNotIn("password", champs)

    def test_donnees_invalides_refusees(self):
        reponse = self.client.post(
            self.url, {"prenom": "Marie", "nom": "Dupont", "telephone": "123", "date_naissance": ""}
        )

        self.assertEqual(reponse.status_code, 200)
        self.client_marie.refresh_from_db()
        self.assertEqual(self.client_marie.telephone, "")


class LienMotDePasseClientTests(TestCase):
    def test_envoyer_un_lien_au_client(self):
        self.client.force_login(creer_agent())
        client = creer_client()

        reponse = self.client.post(reverse("envoyer_lien_client", args=[client.pk]))

        self.assertRedirects(reponse, reverse("modifier_client", args=[client.pk]))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["client@example.com"])

        # Le client suit le lien et choisit lui-même son mot de passe.
        self.client.logout()
        lien = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
        formulaire = self.client.get(lien, follow=True)
        self.client.post(
            formulaire.redirect_chain[-1][0],
            {"new_password1": "montagne-lac-77", "new_password2": "montagne-lac-77"},
        )
        client.refresh_from_db()
        self.assertTrue(client.check_password("montagne-lac-77"))

    def test_get_refuse(self):
        self.client.force_login(creer_agent())
        client = creer_client()

        self.assertEqual(
            self.client.get(reverse("envoyer_lien_client", args=[client.pk])).status_code, 405
        )
