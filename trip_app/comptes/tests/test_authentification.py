import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from comptes import limitation
from comptes.models import Role

from .fabriques import MOT_DE_PASSE, creer_client

Utilisateur = get_user_model()

def donnees_inscription(**champs):
    donnees = {
        "prenom": "Marie",
        "nom": "Dupont",
        "email": "marie@example.com",
        "telephone": "0470 12 34 56",
        "date_naissance": "1955-04-12",
        "password1": "soleil-plage-42",
        "password2": "soleil-plage-42",
        "consentement": "on",
    }
    donnees.update(champs)
    return donnees


class InscriptionTests(TestCase):
    url = reverse("inscription")

    def test_page_accessible(self):
        reponse = self.client.get(self.url)

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "politique de confidentialité")

    def test_inscription_cree_un_client_connecte(self):
        reponse = self.client.post(self.url, donnees_inscription())

        self.assertRedirects(reponse, reverse("accueil"))
        client = Utilisateur.objects.get(email="marie@example.com")
        self.assertEqual(client.role, Role.CLIENT)
        self.assertEqual(client.telephone, "0470123456")
        self.assertIsNotNone(client.date_consentement)
        self.assertTrue(client.check_password("soleil-plage-42"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), client.pk)

    def test_role_impose_meme_si_envoye(self):
        self.client.post(self.url, donnees_inscription(role=Role.ADMINISTRATEUR))

        self.assertEqual(Utilisateur.objects.get().role, Role.CLIENT)

    def test_inscription_refusee(self):
        cas = {
            "sans consentement": {"consentement": ""},
            "sans date de naissance": {"date_naissance": ""},
            "mot de passe faible": {"password1": "court", "password2": "court"},
            "mots de passe différents": {"password2": "autre-chose-42"},
            "téléphone étranger": {"telephone": "+33 6 12 34 56 78"},
        }
        for raison, champs in cas.items():
            with self.subTest(raison=raison):
                reponse = self.client.post(self.url, donnees_inscription(**champs))

                self.assertEqual(reponse.status_code, 200)
                self.assertFalse(Utilisateur.objects.exists())

    def test_email_deja_utilise_quelle_que_soit_la_casse(self):
        creer_client(email="marie@example.com")

        reponse = self.client.post(self.url, donnees_inscription(email="MARIE@example.com"))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Utilisateur.objects.count(), 1)

    def test_utilisateur_connecte_redirige(self):
        self.client.force_login(creer_client())

        self.assertRedirects(self.client.get(self.url), reverse("accueil"))


class ConnexionTests(TestCase):
    url = reverse("connexion")

    def setUp(self):
        cache.clear()
        self.utilisateur = creer_client()

    def connecter(self, email="client@example.com", mot_de_passe=MOT_DE_PASSE):
        return self.client.post(self.url, {"username": email, "password": mot_de_passe})

    def test_connexion_reussie(self):
        reponse = self.connecter()

        self.assertRedirects(reponse, reverse("accueil"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.utilisateur.pk)

    def test_connexion_insensible_a_la_casse(self):
        self.assertRedirects(self.connecter(email="Client@Example.com"), reverse("accueil"))

    def test_mauvais_mot_de_passe(self):
        reponse = self.connecter(mot_de_passe="mauvais-mot-2026")

        self.assertContains(reponse, "Adresse e-mail ou mot de passe incorrect.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_compte_desactive_refuse(self):
        self.utilisateur.is_active = False
        self.utilisateur.save()

        reponse = self.connecter()

        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blocage_apres_trop_d_echecs(self):
        for _ in range(limitation.MAX_ECHECS):
            self.connecter(mot_de_passe="mauvais-mot-2026")

        reponse = self.connecter()

        self.assertContains(reponse, "Trop de tentatives échouées")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_blocage_par_email(self):
        for _ in range(limitation.MAX_ECHECS):
            self.connecter(email="autre@example.com", mot_de_passe="mauvais-mot-2026")

        self.assertRedirects(self.connecter(), reverse("accueil"))

    def test_succes_remet_le_compteur_a_zero(self):
        for _ in range(limitation.MAX_ECHECS - 1):
            self.connecter(mot_de_passe="mauvais-mot-2026")
        self.connecter()
        self.client.logout()

        self.connecter(mot_de_passe="mauvais-mot-2026")

        self.assertFalse(limitation.est_bloque("client@example.com"))

    def test_deconnexion(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.post(reverse("deconnexion"))

        self.assertRedirects(reponse, reverse("accueil"))
        self.assertNotIn("_auth_user_id", self.client.session)


class MotDePasseOublieTests(TestCase):
    url = reverse("mot_de_passe_oublie")

    def test_lien_valable_une_heure(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    def test_email_envoye_et_lien_fonctionnel(self):
        client = creer_client()

        reponse = self.client.post(self.url, {"email": "CLIENT@example.com"})

        self.assertRedirects(reponse, reverse("mot_de_passe_oublie_envoye"))
        self.assertEqual(len(mail.outbox), 1)
        lien = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)

        # Django remplace le jeton par un jeton de session puis redirige.
        formulaire = self.client.get(lien, follow=True)
        self.assertTrue(formulaire.context["validlink"])
        nouveau = "montagne-lac-77"
        reponse = self.client.post(
            formulaire.redirect_chain[-1][0],
            {"new_password1": nouveau, "new_password2": nouveau},
        )

        self.assertRedirects(reponse, reverse("reinitialisation_terminee"))
        client.refresh_from_db()
        self.assertTrue(client.check_password(nouveau))

    def test_email_inconnu_message_neutre(self):
        reponse = self.client.post(self.url, {"email": "inconnu@example.com"})

        self.assertRedirects(reponse, reverse("mot_de_passe_oublie_envoye"))
        self.assertEqual(len(mail.outbox), 0)


class ConfidentialiteTests(TestCase):
    def test_page_accessible_et_liee_dans_le_pied_de_page(self):
        reponse = self.client.get(reverse("confidentialite"))

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, f'href="{reverse("confidentialite")}"')
