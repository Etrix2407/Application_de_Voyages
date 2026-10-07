from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views, views_clients

urlpatterns = [
    path("inscription/", views.sign_up, name="sign_up"),
    path("connexion/", views.AccountLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
    path("profil/modifier/", views.edit_profile, name="edit_profile"),
    path(
        "profil/mot-de-passe/",
        views.AccountPasswordChangeView.as_view(),
        name="change_password",
    ),
    path("profil/supprimer/", views.delete_account, name="delete_account"),
    path("clients/", views_clients.client_list, name="client_list"),
    path("clients/<int:pk>/modifier/", views_clients.edit_client, name="edit_client"),
    path(
        "clients/<int:pk>/envoyer-lien/",
        views_clients.send_client_link,
        name="send_client_link",
    ),
    path("personnel/", views.staff_list, name="staff_list"),
    path("personnel/nouveau/", views.create_agent, name="create_agent"),
    path("personnel/<int:pk>/modifier/", views.edit_staff_member, name="edit_staff_member"),
    path(
        "personnel/<int:pk>/desactiver/",
        views.set_staff_active,
        {"active": False},
        name="deactivate_staff_member",
    ),
    path(
        "personnel/<int:pk>/reactiver/",
        views.set_staff_active,
        {"active": True},
        name="reactivate_staff_member",
    ),
    path("personnel/<int:pk>/renvoyer-lien/", views.resend_link, name="resend_staff_link"),
    path("personnel/<int:pk>/supprimer/", views.delete_staff_member, name="delete_staff_member"),
    path(
        "mot-de-passe-oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "mot-de-passe-oublie/envoye/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reinitialisation/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reinitialisation/terminee/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
