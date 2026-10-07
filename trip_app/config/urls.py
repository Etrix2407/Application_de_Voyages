"""Routes principales du projet."""

from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path(
        "confidentialite/",
        TemplateView.as_view(template_name="privacy.html"),
        name="privacy",
    ),
    path("comptes/", include("accounts.urls")),
    path("catalogue/", include("catalog.urls")),
]
