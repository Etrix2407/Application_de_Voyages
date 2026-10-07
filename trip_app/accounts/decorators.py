"""Contrôle d'accès par rôle."""

from collections.abc import Callable
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def _role_required(is_allowed: Callable) -> Callable:
    """Exige un utilisateur connecté ; refuse l'accès (403) s'il n'a pas le bon rôle."""

    def decorator(view):
        @wraps(view)
        @login_required
        def protected_view(request, *args, **kwargs):
            if not is_allowed(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return protected_view

    return decorator


# Règle 7 : un client n'accède qu'à ses propres données.
client_required = _role_required(lambda user: user.is_client)

# Gestion du personnel : réservée à l'administrateur.
administrator_required = _role_required(lambda user: user.is_administrator)

# Règle 6 : seuls les agents (et l'administrateur) modifient le catalogue.
staff_required = _role_required(lambda user: user.is_staff_member)
