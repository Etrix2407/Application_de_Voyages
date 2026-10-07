from django.urls import path

from . import views, views_favorites
from . import views_manage as manage

urlpatterns = [
    path("", views.country_list, name="country_list"),
    path("recherche/", views.search_page, name="search"),
    path("pays/<int:pk>/", views.country_detail, name="country_detail"),
    path("destinations/<int:pk>/", views.destination_detail, name="destination_detail"),
    path("activites/<int:pk>/", views.activity_detail, name="activity_detail"),
    path("favoris/", views_favorites.favorite_list, name="favorite_list"),
    path(
        "favoris/<str:item_type>/<int:pk>/ajouter/",
        views_favorites.add_favorite,
        name="add_favorite",
    ),
    path(
        "favoris/<str:item_type>/<int:pk>/retirer/",
        views_favorites.remove_favorite,
        name="remove_favorite",
    ),
    path("gestion/", manage.country_list, name="manage_country_list"),
    path("gestion/pays/nouveau/", manage.create_country, name="manage_create_country"),
    path("gestion/pays/<int:pk>/", manage.country_page, name="manage_country"),
    path("gestion/pays/<int:pk>/modifier/", manage.edit_country, name="manage_edit_country"),
    path(
        "gestion/pays/<int:pk>/supprimer/", manage.delete_country, name="manage_delete_country"
    ),
    path(
        "gestion/pays/<int:country_pk>/destinations/nouvelle/",
        manage.create_destination,
        name="manage_create_destination",
    ),
    path(
        "gestion/destinations/<int:pk>/modifier/",
        manage.edit_destination,
        name="manage_edit_destination",
    ),
    path(
        "gestion/destinations/<int:pk>/supprimer/",
        manage.delete_destination,
        name="manage_delete_destination",
    ),
    path(
        "gestion/pays/<int:country_pk>/activites/nouvelle/",
        manage.create_activity,
        name="manage_create_activity",
    ),
    path(
        "gestion/activites/<int:pk>/modifier/",
        manage.edit_activity,
        name="manage_edit_activity",
    ),
    path(
        "gestion/activites/<int:pk>/supprimer/",
        manage.delete_activity,
        name="manage_delete_activity",
    ),
]
