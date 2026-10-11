"""Variables disponibles dans tous les gabarits."""

from datetime import timedelta

from django.conf import settings

from accounts.services import throttling
from accounts.services.email_change import LINK_MAX_AGE
from accounts.services.sign_up import CONFIRMATION_MAX_AGE, UNCONFIRMED_RETENTION
from common.text import duration_text
from reviews.models import EDIT_PERIOD


def site(request):
    return {"site_name": settings.SITE_NAME}


def durations(request):
    """Durées affichées aux utilisateurs, tirées des réglages : les textes suivent le code."""
    longest_limit = max(
        limiter.window_seconds for limiter in vars(throttling).values() if isinstance(limiter, throttling.Limiter)
    )
    return {
        "durations": {
            "sign_up_link": duration_text(CONFIRMATION_MAX_AGE),
            "password_link": duration_text(timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT)),
            "email_change_link": duration_text(LINK_MAX_AGE),
            "unconfirmed_retention": duration_text(UNCONFIRMED_RETENTION),
            "review_edit": duration_text(EDIT_PERIOD),
            "longest_limit": duration_text(timedelta(seconds=longest_limit)),
        }
    }
