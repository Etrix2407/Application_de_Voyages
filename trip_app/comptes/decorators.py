"""Contrôle d'accès par rôle."""

from collections.abc import Callable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def _role_requis(est_autorise: Callable) -> Callable:
    """Exige un utilisateur connecté ; refuse l'accès (403) s'il n'a pas le bon rôle."""

    def decorateur(vue):
        @wraps(vue)
        @login_required
        def vue_protegee(request, *args, **kwargs):
            if not est_autorise(request.user):
                raise PermissionDenied
            return vue(request, *args, **kwargs)

        return vue_protegee

    return decorateur


# Règle 7 : un client n'accède qu'à ses propres données.
client_requis = _role_requis(lambda utilisateur: utilisateur.est_client)

# Gestion du personnel : réservée à l'administrateur.
administrateur_requis = _role_requis(lambda utilisateur: utilisateur.est_administrateur)

# Règle 6 : seuls les agents (et l'administrateur) modifient le catalogue.
personnel_requis = _role_requis(lambda utilisateur: utilisateur.est_personnel)
