from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from catalogue.models import Activite, Destination, Pays

Utilisateur = get_user_model()


def charger_demo() -> str:
    sortie = StringIO()
    call_command("charger_demo", stdout=sortie)
    return sortie.getvalue()


@override_settings(DEBUG=True)
class ChargerDemoTests(TestCase):
    def test_donnees_fictives_marquees_exemple(self):
        charger_demo()

        self.assertEqual(Pays.objects.count(), 3)
        for objets in [Pays.objects.all(), Destination.objects.all(), Activite.objects.all()]:
            for objet in objets:
                with self.subTest(objet=objet.nom):
                    self.assertTrue(objet.nom.startswith("Exemple — "))

    def test_un_pays_desactive_pour_la_demonstration(self):
        charger_demo()

        self.assertEqual(Pays.objects.visibles().count(), 2)

    def test_comptes_de_demonstration_avec_mot_de_passe_aleatoire(self):
        sortie = charger_demo()

        client = Utilisateur.objects.get(email="client.demo@example.com")
        mot_de_passe = sortie.split("client.demo@example.com / mot de passe : ")[1].split()[0]
        self.assertTrue(client.check_password(mot_de_passe))
        self.assertTrue(client.est_client)
        self.assertTrue(Utilisateur.objects.get(email="agent.demo@example.com").est_personnel)

    def test_relancer_ne_cree_pas_de_doublon(self):
        charger_demo()
        sortie = charger_demo()

        self.assertEqual(Pays.objects.count(), 3)
        self.assertEqual(Utilisateur.objects.count(), 2)
        self.assertIn("Déjà présent", sortie)

    @override_settings(DEBUG=False)
    def test_refuse_hors_developpement(self):
        with self.assertRaises(CommandError):
            charger_demo()
        self.assertFalse(Pays.objects.exists())
