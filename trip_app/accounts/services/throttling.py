"""Limitation des actions répétées, par adresse e-mail ou par adresse IP."""

import ipaddress
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache


@dataclass(frozen=True)
class Limiter:
    """Au-delà de `max_attempts` tentatives, l'action est bloquée pendant `window_seconds`.

    L'identifiant (adresse e-mail ou IP) est comparé sans tenir compte des majuscules.
    Le délai part de la première tentative. Le compteur vit dans le cache Django.
    """

    name: str
    max_attempts: int
    window_seconds: int

    def _key(self, identifier: str) -> str:
        return f"{self.name}:{identifier.strip().lower()}"

    def is_locked(self, identifier: str) -> bool:
        return cache.get(self._key(identifier), 0) >= self.max_attempts

    def record(self, identifier: str) -> None:
        key = self._key(identifier)
        # add() ne fait rien si la clé existe : le délai part de la première tentative.
        cache.add(key, 0, self.window_seconds)
        try:
            cache.incr(key)
        except ValueError:
            # La clé a expiré entre add() et incr().
            cache.set(key, 1, self.window_seconds)

    def reset(self, identifier: str) -> None:
        cache.delete(self._key(identifier))


def get_client_ip(request) -> str:
    """Adresse IP du visiteur, telle que comptée par les limites.

    Par défaut, l'IP de la connexion (REMOTE_ADDR), impossible à falsifier. L'en-tête
    X-Forwarded-For, que n'importe qui peut forger, n'est lu que si le site est déclaré
    derrière `NUM_PROXIES` serveurs intermédiaires de confiance : on prend alors l'adresse
    ajoutée par le premier d'entre eux.
    Une adresse IPv6 est ramenée à son réseau /64 : un abonné en reçoit des milliards,
    il ne doit pas pouvoir en changer à chaque essai.
    """
    if request is None:
        return ""
    ip = request.META.get("REMOTE_ADDR", "")
    if settings.NUM_PROXIES:
        header = request.META.get("HTTP_X_FORWARDED_FOR", "")
        forwarded = [address.strip() for address in header.split(",") if address.strip()]
        if len(forwarded) >= settings.NUM_PROXIES:
            ip = forwarded[-settings.NUM_PROXIES]
    return _network_of(ip)


def _network_of(ip: str) -> str:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return ip


# Par adresse e-mail.
login_failures = Limiter("login-failures", max_attempts=5, window_seconds=15 * 60)
password_reset_requests = Limiter("password-reset", max_attempts=3, window_seconds=60 * 60)
confirmation_emails = Limiter("sign-up-emails", max_attempts=3, window_seconds=60 * 60)

# Par compte connecté : ressaisie du mot de passe (changement d'e-mail ou de mot de passe,
# suppression du compte). Empêche de le deviner depuis une session volée.
password_confirmations = Limiter("password-confirmations", max_attempts=5, window_seconds=15 * 60)

# Par adresse IP : seuils larges, car un bureau ou un wifi partage souvent une même IP.
login_failures_by_ip = Limiter("login-failures-ip", max_attempts=20, window_seconds=15 * 60)
sign_ups_by_ip = Limiter("sign-ups-ip", max_attempts=5, window_seconds=60 * 60)
password_reset_requests_by_ip = Limiter("password-reset-ip", max_attempts=10, window_seconds=60 * 60)
confirmation_requests_by_ip = Limiter("confirmation-resend-ip", max_attempts=10, window_seconds=60 * 60)

# Après une inscription, se connecter avec le mot de passe choisi révèle si l'adresse avait
# déjà un compte confirmé (la connexion échoue). Pour freiner ce test d'adresses en série :
# une IP qui s'est inscrite dans l'heure est bloquée 15 minutes après 3 échecs de connexion.
# `recent_sign_ups_by_ip` est remis à zéro à chaque inscription : l'heure part de la dernière.
recent_sign_ups_by_ip = Limiter("recent-sign-up-ip", max_attempts=1, window_seconds=60 * 60)
login_failures_after_sign_up_by_ip = Limiter(
    "login-failures-after-sign-up-ip", max_attempts=3, window_seconds=15 * 60
)
