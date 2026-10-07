from django.urls import path

from . import views, views_favoris
from . import views_gestion as gestion

urlpatterns = [
    path("", views.liste_pays, name="catalogue_pays"),
    path("recherche/", views.recherche, name="recherche"),
    path("pays/<int:pk>/", views.detail_pays, name="detail_pays"),
    path("destinations/<int:pk>/", views.detail_destination, name="detail_destination"),
    path("activites/<int:pk>/", views.detail_activite, name="detail_activite"),
    path("favoris/", views_favoris.mes_favoris, name="mes_favoris"),
    path(
        "favoris/<str:type_element>/<int:pk>/ajouter/",
        views_favoris.ajouter,
        name="ajouter_favori",
    ),
    path(
        "favoris/<str:type_element>/<int:pk>/retirer/",
        views_favoris.retirer,
        name="retirer_favori",
    ),
    path("gestion/", gestion.liste_pays, name="gestion_liste_pays"),
    path("gestion/pays/nouveau/", gestion.creer_pays, name="gestion_creer_pays"),
    path("gestion/pays/<int:pk>/", gestion.fiche_pays, name="gestion_pays"),
    path("gestion/pays/<int:pk>/modifier/", gestion.modifier_pays, name="gestion_modifier_pays"),
    path(
        "gestion/pays/<int:pk>/supprimer/", gestion.supprimer_pays, name="gestion_supprimer_pays"
    ),
    path(
        "gestion/pays/<int:pays_pk>/destinations/nouvelle/",
        gestion.creer_destination,
        name="gestion_creer_destination",
    ),
    path(
        "gestion/destinations/<int:pk>/modifier/",
        gestion.modifier_destination,
        name="gestion_modifier_destination",
    ),
    path(
        "gestion/destinations/<int:pk>/supprimer/",
        gestion.supprimer_destination,
        name="gestion_supprimer_destination",
    ),
    path(
        "gestion/pays/<int:pays_pk>/activites/nouvelle/",
        gestion.creer_activite,
        name="gestion_creer_activite",
    ),
    path(
        "gestion/activites/<int:pk>/modifier/",
        gestion.modifier_activite,
        name="gestion_modifier_activite",
    ),
    path(
        "gestion/activites/<int:pk>/supprimer/",
        gestion.supprimer_activite,
        name="gestion_supprimer_activite",
    ),
]
