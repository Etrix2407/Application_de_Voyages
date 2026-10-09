"""Variables disponibles dans tous les gabarits."""

from django.conf import settings


def site(request):
    return {"site_name": settings.SITE_NAME}
