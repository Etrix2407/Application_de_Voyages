from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views, views_clients

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
    path("clients/", views_clients.liste_clients, name="liste_clients"),
    path("clients/<int:pk>/modifier/", views_clients.modifier_client, name="modifier_client"),
    path(
        "clients/<int:pk>/envoyer-lien/",
        views_clients.envoyer_lien_client,
        name="envoyer_lien_client",
    ),
    path("personnel/", views.liste_personnel, name="liste_personnel"),
    path("personnel/nouveau/", views.creer_agent, name="creer_agent"),
    path("personnel/<int:pk>/modifier/", views.modifier_membre, name="modifier_membre"),
    path(
        "personnel/<int:pk>/desactiver/",
        views.changer_activation,
        {"actif": False},
        name="desactiver_membre",
    ),
    path(
        "personnel/<int:pk>/reactiver/",
        views.changer_activation,
        {"actif": True},
        name="reactiver_membre",
    ),
    path("personnel/<int:pk>/renvoyer-lien/", views.renvoyer_lien, name="renvoyer_lien"),
    path("personnel/<int:pk>/supprimer/", views.supprimer_membre, name="supprimer_membre"),
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
