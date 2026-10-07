from django.test import TestCase
from django.urls import reverse

from catalogue.models import Activite, Destination, Pays
from comptes.tests.fabriques import creer_admin, creer_agent, creer_client

from .fabriques import creer_activite, creer_destination, creer_pays


def donnees_pays(**champs):
    donnees = {
        "nom": "Pérou",
        "continent": "amerique",
        "langue_principale": "espagnol",
        "monnaie": "sol",
        "description": "Description.",
        "visa": "non_requis",
        "decalage_ete": "-7",
        "decalage_hiver": "-6",
        "actif": "on",
    }
    donnees.update(champs)
    return donnees


def donnees_activite(**champs):
    donnees = {
        "nom": "Randonnée",
        "description": "Description.",
        "categorie": "sport",
        "duree_minutes": "240",
        "prix_par_personne": "60.00",
        "difficulte": "difficile",
        "age_minimum": "",
        "destination": "",
        "actif": "on",
    }
    donnees.update(champs)
    return donnees


class AccesGestionTests(TestCase):
    def setUp(self):
        self.pays = creer_pays()
        self.destination = creer_destination(self.pays)
        self.activite = creer_activite(self.pays)

    def urls(self):
        return [
            reverse("gestion_liste_pays"),
            reverse("gestion_creer_pays"),
            reverse("gestion_pays", args=[self.pays.pk]),
            reverse("gestion_modifier_pays", args=[self.pays.pk]),
            reverse("gestion_supprimer_pays", args=[self.pays.pk]),
            reverse("gestion_creer_destination", args=[self.pays.pk]),
            reverse("gestion_modifier_destination", args=[self.destination.pk]),
            reverse("gestion_supprimer_destination", args=[self.destination.pk]),
            reverse("gestion_creer_activite", args=[self.pays.pk]),
            reverse("gestion_modifier_activite", args=[self.activite.pk]),
            reverse("gestion_supprimer_activite", args=[self.activite.pk]),
        ]

    def test_client_refuse(self):
        self.client.force_login(creer_client())

        for url in self.urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Pays.objects.exists())

    def test_visiteur_redirige(self):
        for url in self.urls():
            with self.subTest(url=url):
                self.assertRedirects(self.client.get(url), f"{reverse('connexion')}?next={url}")

    def test_agent_et_administrateur_autorises(self):
        for utilisateur in [creer_agent(), creer_admin()]:
            self.client.force_login(utilisateur)
            with self.subTest(role=utilisateur.role):
                self.assertEqual(self.client.get(reverse("gestion_liste_pays")).status_code, 200)


class GestionPaysTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_agent())

    def test_liste_avec_les_pays_desactives(self):
        creer_pays("Japon")
        creer_pays("Cuba", actif=False)

        reponse = self.client.get(reverse("gestion_liste_pays"))

        self.assertContains(reponse, "Japon")
        self.assertContains(reponse, "Cuba")
        self.assertContains(reponse, "Désactivé")

    def test_creer_un_pays(self):
        reponse = self.client.post(reverse("gestion_creer_pays"), donnees_pays())

        pays = Pays.objects.get(nom="Pérou")
        self.assertRedirects(reponse, reverse("gestion_pays", args=[pays.pk]))
        self.assertTrue(pays.actif)

    def test_nom_en_double_refuse(self):
        creer_pays("Pérou")

        reponse = self.client.post(reverse("gestion_creer_pays"), donnees_pays(nom="PÉROU"))

        self.assertContains(reponse, "Un pays avec ce nom existe déjà.")

    def test_desactiver_un_pays(self):
        pays = creer_pays("Pérou")

        donnees = donnees_pays()
        del donnees["actif"]
        self.client.post(reverse("gestion_modifier_pays", args=[pays.pk]), donnees)

        pays.refresh_from_db()
        self.assertFalse(pays.actif)

    def test_supprimer_un_pays_vide(self):
        pays = creer_pays()
        url = reverse("gestion_supprimer_pays", args=[pays.pk])

        self.assertContains(self.client.get(url), "définitive")
        self.assertRedirects(self.client.post(url), reverse("gestion_liste_pays"))
        self.assertFalse(Pays.objects.exists())

    def test_pays_avec_contenu_non_supprimable(self):
        pays = creer_pays()
        creer_destination(pays)

        reponse = self.client.post(reverse("gestion_supprimer_pays", args=[pays.pk]), follow=True)

        self.assertContains(reponse, "ne peut pas être supprimé")
        self.assertTrue(Pays.objects.filter(pk=pays.pk).exists())

    def test_fiche_affiche_destinations_et_activites(self):
        pays = creer_pays()
        creer_destination(pays, "Kyoto", photo="https://example.com/kyoto.jpg")
        creer_activite(pays, "Sumo")

        reponse = self.client.get(reverse("gestion_pays", args=[pays.pk]))

        self.assertContains(reponse, "Kyoto")
        self.assertContains(reponse, 'alt="Photo : Kyoto"')
        self.assertContains(reponse, "Sumo")


class GestionDestinationTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_agent())
        self.pays = creer_pays()

    def test_creer_une_destination_dans_le_pays(self):
        reponse = self.client.post(
            reverse("gestion_creer_destination", args=[self.pays.pk]),
            {
                "nom": "Kyoto",
                "description": "Temples.",
                "mois_debut": "11",
                "mois_fin": "3",
                "prix_a_partir_de": "1200",
                "photo": "",
                "actif": "on",
            },
        )

        self.assertRedirects(reponse, reverse("gestion_pays", args=[self.pays.pk]))
        destination = Destination.objects.get()
        self.assertEqual(destination.pays, self.pays)
        self.assertEqual(destination.mois_ideaux(), [11, 12, 1, 2, 3])

    def test_le_pays_n_est_pas_modifiable(self):
        destination = creer_destination(self.pays)
        autre = creer_pays("Pérou")

        self.client.post(
            reverse("gestion_modifier_destination", args=[destination.pk]),
            {"nom": "Kyoto", "description": "x", "pays": autre.pk, "actif": "on"},
        )

        destination.refresh_from_db()
        self.assertEqual(destination.pays, self.pays)

    def test_supprimer_garde_les_activites(self):
        destination = creer_destination(self.pays)
        activite = creer_activite(self.pays, destination=destination)
        url = reverse("gestion_supprimer_destination", args=[destination.pk])

        self.assertContains(self.client.get(url), "restent dans le pays")
        self.client.post(url)

        activite.refresh_from_db()
        self.assertIsNone(activite.destination)


class GestionActiviteTests(TestCase):
    def setUp(self):
        self.client.force_login(creer_agent())
        self.pays = creer_pays()

    def test_creer_une_activite_sans_destination(self):
        reponse = self.client.post(
            reverse("gestion_creer_activite", args=[self.pays.pk]), donnees_activite()
        )

        self.assertRedirects(reponse, reverse("gestion_pays", args=[self.pays.pk]))
        activite = Activite.objects.get()
        self.assertEqual(activite.pays, self.pays)
        self.assertIsNone(activite.destination)
        self.assertIsNone(activite.age_minimum)

    def test_destinations_proposees_limitees_au_pays(self):
        kyoto = creer_destination(self.pays, "Kyoto")
        cusco = creer_destination(creer_pays("Pérou"), "Cusco")

        reponse = self.client.get(reverse("gestion_creer_activite", args=[self.pays.pk]))

        choix = list(reponse.context["form"].fields["destination"].queryset)
        self.assertEqual(choix, [kyoto])
        self.assertNotIn(cusco, choix)

    def test_destination_d_un_autre_pays_refusee(self):
        cusco = creer_destination(creer_pays("Pérou"), "Cusco")

        reponse = self.client.post(
            reverse("gestion_creer_activite", args=[self.pays.pk]),
            donnees_activite(destination=cusco.pk),
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Activite.objects.exists())

    def test_modifier_puis_supprimer(self):
        activite = creer_activite(self.pays)

        self.client.post(
            reverse("gestion_modifier_activite", args=[activite.pk]),
            donnees_activite(nom="Sumo", age_minimum="12"),
        )
        activite.refresh_from_db()
        self.assertEqual(activite.nom, "Sumo")
        self.assertEqual(activite.age_minimum, 12)

        self.client.post(reverse("gestion_supprimer_activite", args=[activite.pk]))
        self.assertFalse(Activite.objects.exists())
