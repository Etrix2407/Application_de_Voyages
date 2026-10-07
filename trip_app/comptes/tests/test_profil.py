from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from comptes.models import Role

from .fabriques import MOT_DE_PASSE, creer_agent, creer_client

Utilisateur = get_user_model()

class AccesProfilTests(TestCase):
    def test_pages_reservees_aux_utilisateurs_connectes(self):
        for nom in ["profil", "modifier_profil", "changer_mot_de_passe", "supprimer_compte"]:
            with self.subTest(page=nom):
                url = reverse(nom)

                reponse = self.client.get(url)

                self.assertRedirects(reponse, f"{reverse('connexion')}?next={url}")

    def test_agent_ne_modifie_ni_ne_supprime_via_le_profil_client(self):
        self.client.force_login(creer_agent())

        for nom in ["modifier_profil", "supprimer_compte"]:
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(nom)).status_code, 403)


class ConsultationProfilTests(TestCase):
    def test_client_voit_ses_informations_et_pas_celles_des_autres(self):
        client = creer_client(telephone="0470123456")
        creer_client(email="voisin@example.com", nom="Voisin")
        self.client.force_login(client)

        reponse = self.client.get(reverse("profil"))

        self.assertContains(reponse, "client@example.com")
        self.assertContains(reponse, "0470123456")
        self.assertContains(reponse, reverse("supprimer_compte"))
        self.assertNotContains(reponse, "voisin@example.com")

    def test_agent_voit_son_numero_sans_lien_de_suppression(self):
        agent = creer_agent()
        self.client.force_login(agent)

        reponse = self.client.get(reverse("profil"))

        self.assertContains(reponse, "AG0001")
        self.assertContains(reponse, reverse("changer_mot_de_passe"))
        self.assertNotContains(reponse, reverse("supprimer_compte"))
        self.assertNotContains(reponse, reverse("modifier_profil"))


class ModificationProfilTests(TestCase):
    url = reverse("modifier_profil")

    def setUp(self):
        self.utilisateur = creer_client()
        self.client.force_login(self.utilisateur)

    def donnees(self, **champs):
        donnees = {
            "prenom": "Marie",
            "nom": "Durand",
            "email": "Nouvelle@Example.com",
            "telephone": "+32 2 123 45 67",
            "date_naissance": "1956-05-01",
        }
        donnees.update(champs)
        return donnees

    def test_modification_enregistree(self):
        reponse = self.client.post(self.url, self.donnees())

        self.assertRedirects(reponse, reverse("profil"))
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.nom, "Durand")
        self.assertEqual(self.utilisateur.email, "nouvelle@example.com")
        self.assertEqual(self.utilisateur.telephone, "+3221234567")
        self.assertEqual(self.utilisateur.date_naissance, date(1956, 5, 1))

    def test_email_deja_pris_refuse(self):
        creer_client(email="pris@example.com")

        reponse = self.client.post(self.url, self.donnees(email="PRIS@example.com"))

        self.assertEqual(reponse.status_code, 200)
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.email, "client@example.com")

    def test_garder_son_propre_email(self):
        reponse = self.client.post(self.url, self.donnees(email="client@example.com"))

        self.assertRedirects(reponse, reverse("profil"))

    def test_role_non_modifiable(self):
        self.client.post(self.url, self.donnees(role=Role.ADMINISTRATEUR))

        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.role, Role.CLIENT)

    def test_date_naissance_obligatoire(self):
        reponse = self.client.post(self.url, self.donnees(date_naissance=""))

        self.assertEqual(reponse.status_code, 200)
        self.utilisateur.refresh_from_db()
        self.assertEqual(self.utilisateur.date_naissance, date(1955, 4, 12))


class ChangementMotDePasseTests(TestCase):
    url = reverse("changer_mot_de_passe")

    def changer(self, ancien, nouveau="montagne-lac-77"):
        return self.client.post(
            self.url,
            {"old_password": ancien, "new_password1": nouveau, "new_password2": nouveau},
        )

    def test_changement_garde_la_session(self):
        client = creer_client()
        self.client.force_login(client)

        reponse = self.changer(MOT_DE_PASSE)

        self.assertRedirects(reponse, reverse("profil"))
        client.refresh_from_db()
        self.assertTrue(client.check_password("montagne-lac-77"))
        self.assertEqual(self.client.get(reverse("profil")).status_code, 200)

    def test_ancien_mot_de_passe_requis(self):
        client = creer_client()
        self.client.force_login(client)

        reponse = self.changer("mauvais-mot-2026")

        self.assertEqual(reponse.status_code, 200)
        client.refresh_from_db()
        self.assertTrue(client.check_password(MOT_DE_PASSE))

    def test_nouveau_mot_de_passe_robuste_requis(self):
        client = creer_client()
        self.client.force_login(client)

        self.changer(MOT_DE_PASSE, nouveau="court")

        client.refresh_from_db()
        self.assertTrue(client.check_password(MOT_DE_PASSE))

    def test_agent_peut_changer_son_mot_de_passe(self):
        agent = creer_agent()
        self.client.force_login(agent)

        self.assertRedirects(self.changer(MOT_DE_PASSE), reverse("profil"))


class SuppressionCompteTests(TestCase):
    url = reverse("supprimer_compte")

    def setUp(self):
        self.utilisateur = creer_client()
        self.client.force_login(self.utilisateur)

    def test_page_de_confirmation(self):
        reponse = self.client.get(self.url)

        self.assertContains(reponse, "définitive")

    def test_mauvais_mot_de_passe_ne_supprime_rien(self):
        reponse = self.client.post(self.url, {"mot_de_passe": "mauvais-mot-2026"})

        self.assertContains(reponse, "Mot de passe incorrect.")
        self.assertTrue(Utilisateur.objects.filter(pk=self.utilisateur.pk).exists())

    def test_suppression_definitive_et_deconnexion(self):
        reponse = self.client.post(self.url, {"mot_de_passe": MOT_DE_PASSE}, follow=True)

        self.assertRedirects(reponse, reverse("accueil"))
        self.assertContains(reponse, "Votre compte et vos données ont été supprimés.")
        self.assertFalse(Utilisateur.objects.filter(pk=self.utilisateur.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)
