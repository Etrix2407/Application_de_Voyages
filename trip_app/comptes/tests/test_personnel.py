import re
from datetime import date

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from comptes.models import Role

Utilisateur = get_user_model()

MOT_DE_PASSE = "voyage2026ok"


def creer_admin(email="gerante@example.com"):
    return Utilisateur.objects.create_superuser(email, MOT_DE_PASSE, nom="Durand", prenom="Anne")


def creer_agent(email="agent@example.com", **champs):
    return Utilisateur.objects.create_user(
        email, MOT_DE_PASSE, nom="Martin", prenom="Luc", role=Role.AGENT, **champs
    )


def creer_client(email="client@example.com"):
    return Utilisateur.objects.create_user(
        email, MOT_DE_PASSE, nom="Dupont", prenom="Marie", date_naissance=date(1955, 4, 12)
    )


class AccesPersonnelTests(TestCase):
    def test_reserve_a_l_administrateur(self):
        agent = creer_agent()
        urls_get = [reverse("liste_personnel"), reverse("creer_agent")]

        for utilisateur in [agent, creer_client()]:
            self.client.force_login(utilisateur)
            for url in urls_get:
                with self.subTest(utilisateur=utilisateur.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            with self.subTest(utilisateur=utilisateur.role, action="désactiver"):
                url = reverse("desactiver_membre", args=[agent.pk])
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_visiteur_redirige_vers_connexion(self):
        url = reverse("liste_personnel")

        self.assertRedirects(self.client.get(url), f"{reverse('connexion')}?next={url}")

    def test_comptes_clients_inaccessibles(self):
        client = creer_client()
        self.client.force_login(creer_admin())

        for nom in ["modifier_membre", "supprimer_membre"]:
            with self.subTest(page=nom):
                self.assertEqual(self.client.get(reverse(nom, args=[client.pk])).status_code, 404)


class ListePersonnelTests(TestCase):
    def test_liste_le_personnel_sans_les_clients(self):
        self.client.force_login(creer_admin())
        creer_agent()
        creer_client()

        reponse = self.client.get(reverse("liste_personnel"))

        self.assertContains(reponse, "agent@example.com")
        self.assertContains(reponse, "gerante@example.com")
        self.assertNotContains(reponse, "client@example.com")


class CreationAgentTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_admin())

    def test_creation_envoie_un_lien_pour_choisir_le_mot_de_passe(self):
        reponse = self.client.post(
            reverse("creer_agent"),
            {"prenom": "Luc", "nom": "Martin", "email": "Luc.Martin@Agence.be"},
        )

        self.assertRedirects(reponse, reverse("liste_personnel"))
        agent = Utilisateur.objects.get(email="luc.martin@agence.be")
        self.assertEqual(agent.role, Role.AGENT)
        self.assertEqual(agent.numero_employe, "AG0002")
        self.assertFalse(agent.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["luc.martin@agence.be"])

        # L'agent suit le lien et choisit son mot de passe.
        self.client.logout()
        lien = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
        formulaire = self.client.get(lien, follow=True)
        self.assertTrue(formulaire.context["validlink"])
        self.client.post(
            formulaire.redirect_chain[-1][0],
            {"new_password1": "bureau-voyage-12", "new_password2": "bureau-voyage-12"},
        )
        agent.refresh_from_db()
        self.assertTrue(agent.check_password("bureau-voyage-12"))

    def test_email_deja_utilise_refuse(self):
        creer_client(email="pris@example.com")

        reponse = self.client.post(
            reverse("creer_agent"), {"prenom": "L", "nom": "M", "email": "PRIS@example.com"}
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class ModificationMembreTests(TestCase):
    def setUp(self):
        self.admin = creer_admin()
        self.agent = creer_agent()
        self.client.force_login(self.admin)

    def modifier(self, membre, **champs):
        donnees = {"prenom": membre.prenom, "nom": membre.nom, "email": membre.email}
        donnees["role"] = membre.role
        donnees.update(champs)
        return self.client.post(reverse("modifier_membre", args=[membre.pk]), donnees)

    def test_modifier_les_informations(self):
        reponse = self.modifier(self.agent, nom="Lambert", email="lambert@example.com")

        self.assertRedirects(reponse, reverse("liste_personnel"))
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.nom, "Lambert")
        self.assertEqual(self.agent.email, "lambert@example.com")
        self.assertEqual(self.agent.numero_employe, "AG0002")

    def test_promouvoir_puis_retrograder(self):
        self.modifier(self.agent, role=Role.ADMINISTRATEUR)
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.est_administrateur)

        self.modifier(self.agent, role=Role.AGENT)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role, Role.AGENT)

    def test_retrograder_un_superutilisateur_retire_l_acces_technique(self):
        autre_admin = creer_admin(email="admin2@example.com")

        self.modifier(autre_admin, role=Role.AGENT)

        autre_admin.refresh_from_db()
        self.assertFalse(autre_admin.is_staff)
        self.assertFalse(autre_admin.is_superuser)

    def test_role_client_interdit(self):
        reponse = self.modifier(self.agent, role=Role.CLIENT)

        self.assertEqual(reponse.status_code, 200)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role, Role.AGENT)

    def test_ne_peut_pas_changer_son_propre_role(self):
        reponse = self.modifier(self.admin, role=Role.AGENT)

        self.assertContains(reponse, "votre propre compte")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.est_administrateur)

    def test_peut_modifier_son_propre_nom(self):
        self.assertRedirects(self.modifier(self.admin, nom="Durand-Nouveau"), reverse("liste_personnel"))


class ActivationTests(TestCase):
    def setUp(self):
        self.admin = creer_admin()
        self.agent = creer_agent()
        self.client.force_login(self.admin)

    def test_desactiver_puis_reactiver(self):
        self.client.post(reverse("desactiver_membre", args=[self.agent.pk]))
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.is_active)

        self.client.post(reverse("reactiver_membre", args=[self.agent.pk]))
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.is_active)

    def test_agent_desactive_perd_sa_session(self):
        session_agent = self.client_class()
        session_agent.force_login(self.agent)

        self.client.post(reverse("desactiver_membre", args=[self.agent.pk]))

        reponse = session_agent.get(reverse("profil"))
        self.assertEqual(reponse.status_code, 302)

    def test_get_refuse(self):
        reponse = self.client.get(reverse("desactiver_membre", args=[self.agent.pk]))

        self.assertEqual(reponse.status_code, 405)

    def test_ne_peut_pas_se_desactiver(self):
        reponse = self.client.post(reverse("desactiver_membre", args=[self.admin.pk]), follow=True)

        self.assertContains(reponse, "votre propre compte")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_renvoyer_le_lien(self):
        self.client.post(reverse("renvoyer_lien", args=[self.agent.pk]))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["agent@example.com"])


class SuppressionMembreTests(TestCase):
    def setUp(self):
        self.admin = creer_admin()
        self.agent = creer_agent()
        self.client.force_login(self.admin)

    def test_confirmation_puis_suppression(self):
        url = reverse("supprimer_membre", args=[self.agent.pk])

        self.assertContains(self.client.get(url), "définitive")
        self.assertRedirects(self.client.post(url), reverse("liste_personnel"))
        self.assertFalse(Utilisateur.objects.filter(pk=self.agent.pk).exists())

    def test_ne_peut_pas_se_supprimer(self):
        reponse = self.client.post(reverse("supprimer_membre", args=[self.admin.pk]), follow=True)

        self.assertContains(reponse, "votre propre compte")
        self.assertTrue(Utilisateur.objects.filter(pk=self.admin.pk).exists())
