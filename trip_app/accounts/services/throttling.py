"""Limitation des actions répétées par adresse e-mail (connexions, liens de mot de passe)."""

from dataclasses import dataclass

from django.core.cache import cache

from accounts.models import normalize_email_address


@dataclass(frozen=True)
class Limiter:
    """Au-delà de `max_attempts` tentatives, l'action est bloquée pendant `window_seconds`.

    Le délai part de la première tentative. Le compteur vit dans le cache Django.
    """

    name: str
    max_attempts: int
    window_seconds: int

    def _key(self, email: str) -> str:
        return f"{self.name}:{normalize_email_address(email)}"

    def is_locked(self, email: str) -> bool:
        return cache.get(self._key(email), 0) >= self.max_attempts

    def record(self, email: str) -> None:
        key = self._key(email)
        # add() ne fait rien si la clé existe : le délai part de la première tentative.
        cache.add(key, 0, self.window_seconds)
        try:
            cache.incr(key)
        except ValueError:
            # La clé a expiré entre add() et incr().
            cache.set(key, 1, self.window_seconds)

    def reset(self, email: str) -> None:
        cache.delete(self._key(email))


# Connexion bloquée 15 minutes après 5 échecs pour une même adresse.
login_failures = Limiter("login-failures", max_attempts=5, window_seconds=15 * 60)

# Au plus 3 liens « mot de passe oublié » par heure pour une même adresse (anti-bombardement).
password_reset_requests = Limiter("password-reset", max_attempts=3, window_seconds=60 * 60)
