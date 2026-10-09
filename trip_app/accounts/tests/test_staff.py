import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role

from .factories import create_admin, create_agent, create_client

User = get_user_model()


class StaffAccessTests(TestCase):
    def test_reserved_to_administrator(self):
        agent = create_agent()
        urls_get = [reverse("staff_list"), reverse("create_agent")]

        for user in [agent, create_client()]:
            self.client.force_login(user)
            for url in urls_get:
                with self.subTest(user=user.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
            with self.subTest(user=user.role, action="désactiver"):
                url = reverse("deactivate_staff_member", args=[agent.pk])
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_visitor_redirected_to_login(self):
        url = reverse("staff_list")

        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_client_accounts_inaccessible(self):
        client = create_client()
        self.client.force_login(create_admin())

        for last_name in ["edit_staff_member", "delete_staff_member"]:
            with self.subTest(page=last_name):
                self.assertEqual(self.client.get(reverse(last_name, args=[client.pk])).status_code, 404)


class StaffListTests(TestCase):
    def test_lists_staff_without_clients(self):
        self.client.force_login(create_admin())
        create_agent()
        create_client()

        response = self.client.get(reverse("staff_list"))

        self.assertContains(response, "agent@example.com")
        self.assertContains(response, "gerante@example.com")
        self.assertNotContains(response, "client@example.com")


class AgentCreationTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin())

    def test_creation_sends_link_to_choose_password(self):
        response = self.client.post(
            reverse("create_agent"),
            {"first_name": "Luc", "last_name": "Martin", "email": "Luc.Martin@Agence.be"},
        )

        self.assertRedirects(response, reverse("staff_list"))
        agent = User.objects.get(email="luc.martin@agence.be")
        self.assertEqual(agent.role, Role.AGENT)
        self.assertEqual(agent.employee_number, "AG0002")
        self.assertFalse(agent.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["luc.martin@agence.be"])

        # L'agent suit le lien et choisit son mot de passe.
        self.client.logout()
        link = re.search(r"https?://[^/]+(/\S+)", mail.outbox[0].body).group(1)
        form_page = self.client.get(link, follow=True)
        self.assertTrue(form_page.context["validlink"])
        self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": "bureau-voyage-12", "new_password2": "bureau-voyage-12"},
        )
        agent.refresh_from_db()
        self.assertTrue(agent.check_password("bureau-voyage-12"))

    def test_email_already_used_rejected(self):
        create_client(email="pris@example.com")

        response = self.client.post(
            reverse("create_agent"), {"first_name": "L", "last_name": "M", "email": "PRIS@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class StaffMemberEditTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.agent = create_agent()
        self.client.force_login(self.admin)

    def edit(self, member, **fields):
        data = {"first_name": member.first_name, "last_name": member.last_name, "email": member.email}
        data["role"] = member.role
        data.update(fields)
        return self.client.post(reverse("edit_staff_member", args=[member.pk]), data)

    def test_edit_information(self):
        response = self.edit(self.agent, last_name="Lambert", email="lambert@example.com")

        self.assertRedirects(response, reverse("staff_list"))
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.last_name, "Lambert")
        self.assertEqual(self.agent.email, "lambert@example.com")
        self.assertEqual(self.agent.employee_number, "AG0002")

    def test_promote_then_demote(self):
        self.edit(self.agent, role=Role.ADMINISTRATOR)
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.is_administrator)

        self.edit(self.agent, role=Role.AGENT)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role, Role.AGENT)

    def test_demoting_superuser_removes_status(self):
        other_admin = create_admin(email="admin2@example.com")

        self.edit(other_admin, role=Role.AGENT)

        other_admin.refresh_from_db()
        self.assertFalse(other_admin.is_superuser)

    def test_client_role_forbidden(self):
        response = self.edit(self.agent, role=Role.CLIENT)

        self.assertEqual(response.status_code, 200)
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.role, Role.AGENT)

    def test_cannot_change_own_role(self):
        response = self.edit(self.admin, role=Role.AGENT)

        self.assertContains(response, "votre propre compte")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_administrator)

    def test_can_edit_own_name(self):
        self.assertRedirects(self.edit(self.admin, last_name="Durand-Nouveau"), reverse("staff_list"))


class ActivationTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.agent = create_agent()
        self.client.force_login(self.admin)

    def test_deactivate_then_reactivate(self):
        self.client.post(reverse("deactivate_staff_member", args=[self.agent.pk]))
        self.agent.refresh_from_db()
        self.assertFalse(self.agent.is_active)

        self.client.post(reverse("reactivate_staff_member", args=[self.agent.pk]))
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.is_active)

    def test_deactivated_agent_loses_session(self):
        agent_session = self.client_class()
        agent_session.force_login(self.agent)

        self.client.post(reverse("deactivate_staff_member", args=[self.agent.pk]))

        response = agent_session.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)

    def test_get_denied(self):
        response = self.client.get(reverse("deactivate_staff_member", args=[self.agent.pk]))

        self.assertEqual(response.status_code, 405)

    def test_cannot_deactivate_self(self):
        response = self.client.post(reverse("deactivate_staff_member", args=[self.admin.pk]), follow=True)

        self.assertContains(response, "votre propre compte")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_resend_link(self):
        self.client.post(reverse("resend_staff_link", args=[self.agent.pk]))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["agent@example.com"])


class StaffMemberDeletionTests(TestCase):
    def setUp(self):
        self.admin = create_admin()
        self.agent = create_agent()
        self.client.force_login(self.admin)

    def test_confirmation_then_deletion(self):
        url = reverse("delete_staff_member", args=[self.agent.pk])

        self.assertContains(self.client.get(url), "définitive")
        self.assertRedirects(self.client.post(url), reverse("staff_list"))
        self.assertFalse(User.objects.filter(pk=self.agent.pk).exists())

    def test_cannot_delete_self(self):
        response = self.client.post(reverse("delete_staff_member", args=[self.admin.pk]), follow=True)

        self.assertContains(response, "votre propre compte")
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


@mock.patch("accounts.services.emails.send_mail", side_effect=OSError("serveur SMTP injoignable"))
class EmailFailureTests(TestCase):
    def setUp(self):
        self.client.force_login(create_admin())

    def test_agent_created_with_clear_message_when_email_fails(self, _send_mail):
        response = self.client.post(
            reverse("create_agent"),
            {"first_name": "Luc", "last_name": "Martin", "email": "luc@example.com"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email="luc@example.com").exists())
        self.assertContains(response, "n&#x27;a pas pu être envoyé")

    def test_resend_link_failure_is_reported(self, _send_mail):
        agent = create_agent()

        response = self.client.post(reverse("resend_staff_link", args=[agent.pk]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "n&#x27;a pas pu être envoyé")


class InactiveMemberLinkTests(TestCase):
    def test_no_password_link_for_inactive_member(self):
        self.client.force_login(create_admin())
        agent = create_agent(is_active=False)

        response = self.client.post(reverse("resend_staff_link", args=[agent.pk]), follow=True)

        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "désactivé")
