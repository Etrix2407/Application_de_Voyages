"""Limitation des tentatives de connexion échouées, par adresse e-mail."""

from django.core.cache import cache

from accounts.models import normalize_email_address

MAX_FAILURES = 5
LOCKOUT_SECONDS = 15 * 60


def _key(email: str) -> str:
    return f"login-failures:{normalize_email_address(email)}"


def is_locked(email: str) -> bool:
    return cache.get(_key(email), 0) >= MAX_FAILURES


def record_failure(email: str) -> None:
    key = _key(email)
    # add() ne fait rien si la clé existe : le délai de blocage part du premier échec.
    cache.add(key, 0, LOCKOUT_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        # La clé a expiré entre add() et incr().
        cache.set(key, 1, LOCKOUT_SECONDS)


def reset(email: str) -> None:
    cache.delete(_key(email))
