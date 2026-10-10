from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .forms import PasswordResetRequestForm
from .views import auth, clients, data_export, email_failures, profile, staff

urlpatterns = [
    path("inscription/", auth.sign_up, name="sign_up"),
    path("inscription/envoyee/", auth.sign_up_done, name="sign_up_done"),
    path("inscription/confirmer/<str:token>/", auth.confirm_sign_up, name="confirm_sign_up"),
    path("inscription/renvoyer-lien/", auth.resend_confirmation, name="resend_confirmation"),
    path("connexion/", auth.AccountLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("profil/", profile.profile, name="profile"),
    path("profil/modifier/", profile.edit_profile, name="edit_profile"),
    path("profil/adresse-email/", profile.change_email, name="change_email"),
    path(
        "profil/adresse-email/confirmer/<str:token>/",
        profile.confirm_email_change,
        name="confirm_email_change",
    ),
    path(
        "profil/mot-de-passe/",
        profile.AccountPasswordChangeView.as_view(),
        name="change_password",
    ),
    path("profil/supprimer/", profile.delete_account, name="delete_account"),
    path("profil/mes-donnees/", data_export.download_my_data, name="download_my_data"),
    path("clients/", clients.client_list, name="client_list"),
    path("clients/<int:pk>/modifier/", clients.edit_client, name="edit_client"),
    path(
        "clients/<int:pk>/envoyer-lien/",
        clients.send_client_link,
        name="send_client_link",
    ),
    path("emails-en-echec/", email_failures.email_failure_list, name="email_failure_list"),
    path("emails-en-echec/<int:pk>/renvoyer/", email_failures.resend_email, name="resend_email"),
    path("personnel/", staff.staff_list, name="staff_list"),
    path("personnel/nouveau/", staff.create_agent, name="create_agent"),
    path("personnel/<int:pk>/modifier/", staff.edit_staff_member, name="edit_staff_member"),
    path(
        "personnel/<int:pk>/desactiver/",
        staff.set_staff_active,
        {"active": False},
        name="deactivate_staff_member",
    ),
    path(
        "personnel/<int:pk>/reactiver/",
        staff.set_staff_active,
        {"active": True},
        name="reactivate_staff_member",
    ),
    path("personnel/<int:pk>/renvoyer-lien/", staff.resend_link, name="resend_staff_link"),
    path("personnel/<int:pk>/supprimer/", staff.delete_staff_member, name="delete_staff_member"),
    path(
        "mot-de-passe-oublie/",
        auth_views.PasswordResetView.as_view(
            form_class=PasswordResetRequestForm,
            template_name="accounts/auth/password_reset.html",
            email_template_name="accounts/emails/password_reset.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe-oublie/envoye/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/auth/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reinitialisation/<uidb64>/<token>/",
        auth.AccountPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("activation/<uidb64>/<token>/", auth.AgentActivationView.as_view(), name="activate_account"),
    path(
        "reinitialisation/terminee/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/auth/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
