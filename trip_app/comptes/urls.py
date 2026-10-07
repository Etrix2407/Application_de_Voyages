from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("profil/", views.profil, name="profil"),
    path("profil/modifier/", views.modifier_profil, name="modifier_profil"),
    path(
        "profil/mot-de-passe/",
        views.ChangementMotDePasseView.as_view(),
        name="changer_mot_de_passe",
    ),
    path("profil/supprimer/", views.supprimer_compte, name="supprimer_compte"),
    path(
        "mot-de-passe-oublie/",
        auth_views.PasswordResetView.as_view(
            template_name="comptes/mot_de_passe_oublie.html",
            email_template_name="comptes/email_reinitialisation.txt",
            subject_template_name="comptes/email_reinitialisation_sujet.txt",
            success_url=reverse_lazy("mot_de_passe_oublie_envoye"),
        ),
        name="mot_de_passe_oublie",
    ),
    path(
        "mot-de-passe-oublie/envoye/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="comptes/mot_de_passe_oublie_envoye.html"
        ),
        name="mot_de_passe_oublie_envoye",
    ),
    path(
        "reinitialisation/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="comptes/reinitialisation.html",
            success_url=reverse_lazy("reinitialisation_terminee"),
        ),
        name="reinitialisation",
    ),
    path(
        "reinitialisation/terminee/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="comptes/reinitialisation_terminee.html"
        ),
        name="reinitialisation_terminee",
    ),
]
