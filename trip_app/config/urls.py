"""Routes principales du projet."""

from django.conf import settings
from django.conf.urls.static import static
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
    path("demandes/", include("orders.urls")),
    path("avis/", include("reviews.urls")),
]

# En développement uniquement : Django sert lui-même les photos envoyées.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
