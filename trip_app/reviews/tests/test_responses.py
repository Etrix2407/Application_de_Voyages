from django.test import TestCase
from django.urls import reverse

from accounts.tests.factories import create_admin, create_agent, create_client
from catalog.tests.factories import create_country, create_destination
from reviews.models import AgencyResponse, ReviewStatus
from reviews.services.responses import ResponseNotAllowed, save_response
from reviews.services.writing import update_review

from .factories import create_review, create_trip_done


class AgencyResponseTests(TestCase):
    def setUp(self):
        self.luc = create_agent(first_name="Luc", last_name="Martin")
        self.julie = create_client(first_name="Julie", last_name="Dupont")
        self.destination = create_destination(create_country(), "Kyoto")
        self.review = create_review(
            create_trip_done(self.julie, self.destination), title="Superbe", status=ReviewStatus.PUBLISHED
        )
        self.url = reverse("manage_respond_review", args=[self.review.pk])

    def respond(self, user, text="Merci pour votre retour !"):
        self.client.force_login(user)
        return self.client.post(self.url, {"text": text}, follow=True)

    def test_agent_responds_signed_with_first_name_only(self):
        self.respond(self.luc)

        response = AgencyResponse.objects.get()
        self.assertEqual((response.author, response.author_first_name), (self.luc, "Luc"))
        page = self.client.get(reverse("destination_detail", args=[self.destination.pk]))
        self.assertContains(page, "Réponse de l'agence — Luc")
        self.assertContains(page, "Merci pour votre retour !")
        self.assertNotContains(page, "Martin")

    def test_administrator_can_respond_too(self):
        self.respond(create_admin(first_name="Anne"))

        self.assertEqual(AgencyResponse.objects.get().author_first_name, "Anne")

    def test_client_sees_the_response_in_my_reviews(self):
        save_response(self.review, self.luc, "Merci Julie !")
        self.client.force_login(self.julie)

        self.assertContains(self.client.get(reverse("my_reviews")), "Merci Julie !")

    def test_one_response_per_review_modified_by_its_author(self):
        self.respond(self.luc, "Première version")
        self.respond(self.luc, "Version corrigée")

        self.assertEqual(AgencyResponse.objects.get().text, "Version corrigée")

    def test_other_agent_cannot_modify_it(self):
        save_response(self.review, self.luc, "Réponse de Luc")

        response = self.respond(create_agent(email="paul@example.com", first_name="Paul"), "Réponse de Paul")

        self.assertContains(response, "Vous ne pouvez pas répondre")
        self.assertEqual(AgencyResponse.objects.get().text, "Réponse de Luc")

    def test_administrator_takes_over_when_author_is_gone(self):
        save_response(self.review, self.luc, "Réponse de Luc")
        self.luc.delete()

        self.respond(create_admin(first_name="Anne"), "Réponse reprise")

        response = AgencyResponse.objects.get()
        self.assertEqual(response.text, "Réponse reprise")
        self.assertEqual(response.author_first_name, "Luc")  # signature d'origine conservée

    def test_only_on_published_reviews(self):
        for status in [ReviewStatus.PENDING, ReviewStatus.REFUSED]:
            with self.subTest(status=status):
                self.review.status = status
                self.review.save()

                self.respond(self.luc)

                self.assertFalse(AgencyResponse.objects.exists())
                with self.assertRaises(ResponseNotAllowed):
                    save_response(self.review, self.luc, "Merci")

    def test_response_required(self):
        response = self.respond(self.luc, "   ")

        self.assertContains(response, "Écrivez la réponse.")
        self.assertFalse(AgencyResponse.objects.exists())

    def test_deleted_when_client_modifies_the_review(self):
        save_response(self.review, self.luc, "Merci !")

        update_review(self.review)

        self.assertFalse(AgencyResponse.objects.exists())

    def test_hidden_with_its_review(self):
        save_response(self.review, self.luc, "Merci !")
        self.review.status = ReviewStatus.REFUSED
        self.review.refusal_reason = "abusive"
        self.review.save()

        page = self.client.get(reverse("destination_detail", args=[self.destination.pk]))

        self.assertNotContains(page, "Merci !")

    def test_client_cannot_respond(self):
        self.client.force_login(self.julie)

        self.assertEqual(self.client.post(self.url, {"text": "Moi aussi"}).status_code, 403)
        self.assertFalse(AgencyResponse.objects.exists())
