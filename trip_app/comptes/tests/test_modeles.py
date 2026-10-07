from datetime import date, timedelta

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from comptes.models import Role
from comptes.validators import valider_telephone_belge

Utilisateur = get_user_model()

MOT_DE_PASSE = "voyage2026ok"


def creer_client(email="client@example.com", **champs):
    champs.setdefault("nom", "Dupont")
    champs.setdefault("prenom", "Marie")
    champs.setdefault("date_naissance", date(1955, 4, 12))
    return Utilisateur.objects.create_user(email, MOT_DE_PASSE, **champs)


def creer_agent(email="agent@example.com", **champs):
    champs.setdefault("nom", "Martin")
    champs.setdefault("prenom", "Luc")
    return Utilisateur.objects.create_user(email, MOT_DE_PASSE, role=Role.AGENT, **champs)


class CreationUtilisateurTests(TestCase):
    def test_client_par_defaut(self):
        client = creer_client()

        self.assertEqual(client.role, Role.CLIENT)
        self.assertTrue(client.est_client)
        self.assertFalse(client.est_personnel)
        self.assertIsNone(client.numero_employe)

    def test_mot_de_passe_hache(self):
        client = creer_client()

        self.assertNotEqual(client.password, MOT_DE_PASSE)
        self.assertTrue(client.check_password(MOT_DE_PASSE))

    def test_connexion_par_email(self):
        creer_client()

        self.assertIsNotNone(authenticate(email="client@example.com", password=MOT_DE_PASSE))

    def test_email_mis_en_minuscules(self):
        client = creer_client(email="  Client@Example.COM ")

        self.assertEqual(client.email, "client@example.com")

    def test_email_unique_sans_tenir_compte_des_majuscules(self):
        creer_client(email="client@example.com")

        with self.assertRaises(IntegrityError):
            creer_agent(email="CLIENT@example.com")

    def test_email_obligatoire(self):
        with self.assertRaises(ValueError):
            Utilisateur.objects.create_user("", MOT_DE_PASSE)


class NumeroEmployeTests(TestCase):
    def test_numeros_attribues_dans_l_ordre(self):
        premier = creer_agent(email="a1@example.com")
        second = creer_agent(email="a2@example.com")

        self.assertEqual(premier.numero_employe, "AG0001")
        self.assertEqual(second.numero_employe, "AG0002")

    def test_numero_conserve_a_la_modification(self):
        agent = creer_agent()
        agent.nom = "Nouveau"
        agent.save()

        agent.refresh_from_db()
        self.assertEqual(agent.numero_employe, "AG0001")

    def test_superutilisateur_est_administrateur(self):
        gerante = Utilisateur.objects.create_superuser(
            "gerante@example.com", MOT_DE_PASSE, nom="Durand", prenom="Anne"
        )

        self.assertEqual(gerante.role, Role.ADMINISTRATEUR)
        self.assertTrue(gerante.est_administrateur)
        self.assertTrue(gerante.est_personnel)
        self.assertEqual(gerante.numero_employe, "AG0001")

    def test_superutilisateur_avec_autre_role_refuse(self):
        with self.assertRaises(ValueError):
            Utilisateur.objects.create_superuser(
                "x@example.com", MOT_DE_PASSE, nom="X", prenom="Y", role=Role.AGENT
            )


class ValidationClientTests(TestCase):
    def nouveau_client(self, **champs):
        champs.setdefault("date_naissance", date(1950, 1, 1))
        return Utilisateur(email="c@example.com", nom="N", prenom="P", **champs)

    def test_client_valide(self):
        client = self.nouveau_client(telephone="0470 12 34 56")

        client.full_clean(exclude=["password"])

        self.assertEqual(client.telephone, "0470123456")

    def test_telephone_facultatif(self):
        self.nouveau_client().full_clean(exclude=["password"])

    def test_date_naissance_obligatoire(self):
        client = self.nouveau_client(date_naissance=None)

        with self.assertRaises(ValidationError) as erreur:
            client.full_clean(exclude=["password"])
        self.assertIn("date_naissance", erreur.exception.message_dict)

    def test_date_naissance_future_refusee(self):
        client = self.nouveau_client(date_naissance=timezone.localdate() + timedelta(days=1))

        with self.assertRaises(ValidationError) as erreur:
            client.full_clean(exclude=["password"])
        self.assertIn("date_naissance", erreur.exception.message_dict)

    def test_agent_sans_date_naissance(self):
        agent = Utilisateur(email="a@example.com", nom="N", prenom="P", role=Role.AGENT)

        agent.full_clean(exclude=["password"])


class TelephoneBelgeTests(SimpleTestCase):
    def test_numeros_valides(self):
        for numero in ["0470 12 34 56", "+32 470 12 34 56", "0032470123456", "02/123.45.67"]:
            with self.subTest(numero=numero):
                valider_telephone_belge(numero)

    def test_numeros_invalides(self):
        for numero in ["12345", "+33 6 12 34 56 78", "0470 12 34 56 78 9", "abc"]:
            with self.subTest(numero=numero), self.assertRaises(ValidationError):
                valider_telephone_belge(numero)


class RobustesseMotDePasseTests(TestCase):
    def test_mot_de_passe_robuste_accepte(self):
        validate_password("soleil-plage-42")

    def test_mots_de_passe_refuses(self):
        cas = {
            "trop court": "court12",
            "sans chiffre": "seulementdeslettres",
            "sans lettre": "123456789012",
            "trop courant": "password1234",
        }
        for raison, mot_de_passe in cas.items():
            with self.subTest(raison=raison), self.assertRaises(ValidationError):
                validate_password(mot_de_passe)

    def test_mot_de_passe_proche_de_l_email_refuse(self):
        client = Utilisateur(email="marie.dupont2024@example.com", nom="Dupont", prenom="Marie")

        with self.assertRaises(ValidationError):
            validate_password("marie.dupont2024", user=client)
