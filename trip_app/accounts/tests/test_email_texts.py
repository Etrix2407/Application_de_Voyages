from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import AccountEmail, EmailLog, EmailText
from accounts.services.email_texts import (
    DefaultText,
    email_kind_label,
    fill_fields,
    find_email_kind,
    register_email_kinds,
)
from accounts.services.emails import send_email

from .email_delivery import SendEmailsImmediately
from .factories import create_admin, create_agent

FIELDS = {"prénom": "Marie", "lien": "https://horizons-lointains.be/reinitialisation/abc/jeton/"}


class EmailTextPageTests(SendEmailsImmediately, TestCase):
    """Modèles des e-mails : modification par l'administrateur, validation, retour au texte d'origine."""

    def setUp(self):
        self.client.force_login(create_admin(first_name="Anne", last_name="Durand"))
        self.url = reverse("edit_email_text", args=[AccountEmail.CLIENT_PASSWORD_LINK])

    def send(self):
        send_email("marie@example.com", AccountEmail.CLIENT_PASSWORD_LINK, FIELDS)
        return mail.outbox[-1]

    def test_administrator_text_is_sent_with_fields_filled(self):
        """Le texte de l'administrateur remplace l'objet et le texte d'origine ; les champs sont remplis."""
        response = self.client.post(
            self.url, {"subject": "Votre nouveau mot de passe", "body": "Chère {prénom},\r\n\r\nVotre lien : {lien}"}
        )

        self.assertRedirects(response, reverse("email_text_list"))
        self.assertEqual(EmailText.objects.get().updated_by_name, "Anne Durand")
        message = self.send()
        self.assertEqual(message.subject, "Votre nouveau mot de passe")
        self.assertTrue(message.body.startswith(f"Chère Marie,\n\nVotre lien : {FIELDS['lien']}\n"))
        self.assertEqual(EmailLog.objects.get().subject, "Votre nouveau mot de passe")

    def test_missing_and_unknown_fields_are_refused(self):
        """Un champ supprimé ou inventé est refusé, avec son nom dans le message."""
        response = self.client.post(self.url, {"subject": "Objet", "body": "Bonjour {nom}, cliquez ici."})

        self.assertContains(response, "Champ variable inconnu : {nom}.")
        self.assertContains(response, "Champs variables manquants : {prénom}, {lien}.")
        self.assertFalse(EmailText.objects.exists())

    def test_lone_brace_and_field_in_subject_are_refused(self):
        """Pas de champ dans l'objet, pas d'accolade seule dans le texte."""
        response = self.client.post(self.url, {"subject": "Bonjour {prénom}", "body": "{prénom} {lien} }"})

        self.assertContains(response, "L&#x27;objet ne peut pas contenir de champ variable")
        self.assertContains(response, "Accolade seule")
        self.assertFalse(EmailText.objects.exists())

    def test_reset_restores_original_text(self):
        """« Rétablir le texte d'origine » supprime le texte modifié : le texte d'origine repart."""
        EmailText.objects.create(
            kind=AccountEmail.CLIENT_PASSWORD_LINK, subject="Ancien objet", body="{prénom} {lien}", updated_by_name="Anne"
        )

        reset_url = reverse("reset_email_text", args=[AccountEmail.CLIENT_PASSWORD_LINK])
        # Une page de confirmation d'abord : rien n'est perdu sur un simple clic.
        self.assertContains(self.client.get(reset_url), "Rétablir le texte d'origine")
        self.assertTrue(EmailText.objects.exists())

        self.client.post(reset_url)

        self.assertFalse(EmailText.objects.exists())
        message = self.send()
        self.assertEqual(message.subject, "Changement de votre mot de passe")
        self.assertIn("Bonjour Marie,", message.body)

    def test_agents_cannot_change_texts(self):
        """Réservé à l'administrateur."""
        self.client.force_login(create_agent())

        response = self.client.post(self.url, {"subject": "Objet", "body": "{prénom} {lien}"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(EmailText.objects.exists())


class FillFieldsTests(TestCase):
    """Remplissage des champs variables."""

    def test_values_with_braces_are_not_read_again(self):
        """Une valeur qui contient des accolades n'est pas prise pour un champ."""
        text = fill_fields("Bonjour {prénom}, voici {lien}", {"prénom": "{lien}", "lien": "le lien"})

        self.assertEqual(text, "Bonjour {lien}, voici le lien")

    def test_empty_optional_line_leaves_no_blank_lines(self):
        """Une ligne facultative vide disparaît sans laisser de lignes vides en trop."""
        text = fill_fields("Annulée.\n\n{explication}\n\nÀ bientôt.", {"explication": ""})

        self.assertEqual(text, "Annulée.\n\nÀ bientôt.")


class EmailKindRegistryTests(SimpleTestCase):
    def test_declaration_refused_without_text_or_twice(self):
        class SampleEmail(models.TextChoices):
            SAMPLE = "sample_email", "Exemple"

        class DuplicateEmail(models.TextChoices):
            PASSWORD_RESET = AccountEmail.PASSWORD_RESET.value, "Doublon"

        text = DefaultText(subject="Objet", body="Texte", fields={})
        cases = {
            "texte manquant": (SampleEmail, {}),
            "valeur déjà déclarée": (DuplicateEmail, {DuplicateEmail.PASSWORD_RESET: text}),
        }
        for case, (kinds, texts) in cases.items():
            with self.subTest(case), self.assertRaises(ImproperlyConfigured):
                register_email_kinds(kinds, texts)
        # Rien n'est enregistré après un refus.
        self.assertIsNone(find_email_kind("sample_email"))
        self.assertEqual(email_kind_label(AccountEmail.PASSWORD_RESET), AccountEmail.PASSWORD_RESET.label)

