"""Cas particuliers du Recap 3 et parcours complet d'un avis, de bout en bout."""

from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import PASSWORD, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from orders.models import Status
from reviews.models import ANONYMOUS_NAME, Review, ReviewStatus
from reviews.services.ratings import attach_ratings

from .factories import create_review, create_trip_done


class DeletedAccountTests(TestCase):
    """Compte supprimé : avis conservés, anonymes, sans lien avec la personne, toujours comptés."""

    def setUp(self):
        self.julie = create_client(first_name="Julie", last_name="Dupont", email="julie@example.com")
        self.destination = create_destination(create_country(), "Kyoto")
        self.review = create_review(
            create_trip_done(self.julie, self.destination), rating=4, status=ReviewStatus.PUBLISHED, title="Superbe"
        )

    def delete_account(self):
        self.client.force_login(self.julie)
        self.client.post(reverse("delete_account"), {"password": PASSWORD})
        self.client.logout()

    def test_deletion_page_announces_it(self):
        self.client.force_login(self.julie)

        self.assertContains(self.client.get(reverse("delete_account")), "Vos avis restent publiés")

    def test_review_kept_anonymous_and_counted(self):
        self.delete_account()

        review = Review.objects.get(pk=self.review.pk)
        self.assertIsNone(review.order.client)
        self.assertEqual(review.author_name, ANONYMOUS_NAME)
        self.assertEqual(attach_ratings([self.destination])[0].rating_summary.count, 1)
        page = self.client.get(reverse("destination_detail", args=[self.destination.pk]))
        self.assertContains(page, "Superbe")
        self.assertContains(page, ANONYMOUS_NAME)
        self.assertNotContains(page, "Julie")

    def test_confirmed_trip_stays_confirmed_and_review_published(self):
        self.delete_account()

        review = Review.objects.select_related("order").get(pk=self.review.pk)
        self.assertEqual(review.order.status, Status.CONFIRMED)
        self.assertEqual(review.status, ReviewStatus.PUBLISHED)

    def test_name_removed_for_staff_too(self):
        self.delete_account()
        self.client.force_login(create_agent())

        for url in [reverse("manage_reviews"), reverse("manage_review_detail", args=[self.review.pk])]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "Client supprimé")
                self.assertNotContains(response, "Dupont")
                self.assertNotContains(response, "julie@example.com")


class InactiveDestinationTests(TestCase):
    """Destination ou pays désactivé : avis gardés en base, invisibles, de retour à la réactivation."""

    def setUp(self):
        self.country = create_country("Japon")
        self.destination = create_destination(self.country, "Kyoto")
        create_review(create_trip_done(create_client(), self.destination), status=ReviewStatus.PUBLISHED,
                      title="Temples superbes")

    def public_pages(self):
        return [reverse("destination_list"), reverse("country_list"), reverse("search") + "?keyword=temples"]

    def test_hidden_everywhere_then_back(self):
        for item in [self.destination, self.country]:
            with self.subTest(item=item):
                item.active = False
                item.save()
                for url in self.public_pages():
                    self.assertNotContains(self.client.get(url), "1 avis")
                self.assertTrue(Review.objects.filter(title="Temples superbes").exists())

                item.active = True
                item.save()
                self.assertContains(self.client.get(reverse("destination_list")), "1 avis")

    def test_staff_still_sees_the_review(self):
        self.destination.active = False
        self.destination.save()
        self.client.force_login(create_agent())

        self.assertContains(self.client.get(reverse("manage_reviews")), "Temples superbes")


class ReviewJourneyTests(TestCase):
    """Parcours complet par les pages : avis, modération, réponse, modification, nouvelle validation."""

    def test_full_journey(self):
        julie = create_client(first_name="Julie", last_name="Dupont")
        luc = create_agent(first_name="Luc")
        destination = create_destination(create_country(), "Kyoto")
        trip = create_trip_done(julie, destination)
        public_page = reverse("destination_detail", args=[destination.pk])

        # 1. Julie, rentrée de voyage, donne son avis.
        self.client.force_login(julie)
        self.client.post(
            reverse("create_review", args=[trip.pk]),
            {"rating": "4", "title": "Très beau voyage", "comment": "Guide passionnant."},
        )
        review = Review.objects.get()
        self.assertNotContains(self.client.get(public_page), "Très beau voyage")

        # 2. Luc le voit dans la file, le publie et y répond.
        self.client.force_login(luc)
        self.assertContains(self.client.get(reverse("home")), "Avis à modérer (1)")
        self.client.post(reverse("manage_publish_review", args=[review.pk]))
        self.client.post(reverse("manage_respond_review", args=[review.pk]), {"text": "Merci Julie, à bientôt !"})
        page = self.client.get(public_page)
        self.assertContains(page, "Très beau voyage")
        self.assertContains(page, "✓ Voyage vérifié")
        self.assertContains(page, "Julie D.")
        self.assertContains(page, "Merci Julie, à bientôt !")
        self.assertContains(page, "4,0 sur 5 (1 avis)")

        # 3. Julie modifie son avis : masqué, réponse supprimée, retour dans la file.
        self.client.force_login(julie)
        self.client.post(
            reverse("edit_review", args=[review.pk]),
            {"rating": "5", "title": "Voyage parfait", "comment": "Guide passionnant, hôtel calme."},
        )
        self.assertNotContains(self.client.get(public_page), "Voyage parfait")
        self.assertNotContains(self.client.get(public_page), "Merci Julie")

        # 4. Luc valide la nouvelle version : la note suit.
        self.client.force_login(luc)
        self.client.post(reverse("manage_publish_review", args=[review.pk]))
        page = self.client.get(public_page)
        self.assertContains(page, "Voyage parfait")
        self.assertContains(page, "5,0 sur 5 (1 avis)")
        self.assertNotContains(page, "Merci Julie")
