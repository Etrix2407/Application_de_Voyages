"""Contrôle d'accès par rôle."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def client_requis(vue):
    """Réserve la vue aux clients connectés (règle 7 : chacun ne voit que ses données)."""

    @wraps(vue)
    @login_required
    def vue_protegee(request, *args, **kwargs):
        if not request.user.est_client:
            raise PermissionDenied
        return vue(request, *args, **kwargs)

    return vue_protegee
