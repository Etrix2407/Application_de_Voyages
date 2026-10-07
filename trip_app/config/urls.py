"""Routes principales du projet."""

from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="accueil.html"), name="accueil"),
    path(
        "confidentialite/",
        TemplateView.as_view(template_name="confidentialite.html"),
        name="confidentialite",
    ),
    path("comptes/", include("comptes.urls")),
    path("catalogue/", include("catalogue.urls")),
]
