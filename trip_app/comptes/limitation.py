"""Limitation des tentatives de connexion échouées, par adresse e-mail."""

from django.core.cache import cache

MAX_ECHECS = 5
DUREE_BLOCAGE_SECONDES = 15 * 60


def _cle(email: str) -> str:
    return f"connexion-echecs:{email.strip().lower()}"


def est_bloque(email: str) -> bool:
    return cache.get(_cle(email), 0) >= MAX_ECHECS


def enregistrer_echec(email: str) -> None:
    cle = _cle(email)
    # add() ne fait rien si la clé existe : le délai de blocage part du premier échec.
    cache.add(cle, 0, DUREE_BLOCAGE_SECONDES)
    try:
        cache.incr(cle)
    except ValueError:
        # La clé a expiré entre add() et incr().
        cache.set(cle, 1, DUREE_BLOCAGE_SECONDES)


def reinitialiser(email: str) -> None:
    cache.delete(_cle(email))
