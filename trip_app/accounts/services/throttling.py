"""Limitation des actions répétées, par adresse e-mail ou par adresse IP."""

import ipaddress
import math
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache

from common.text import duration_text


@dataclass(frozen=True)
class Limiter:
    """Au-delà de `max_attempts` tentatives, l'action est bloquée jusqu'à la fin de la fenêtre.

    L'identifiant (adresse e-mail, IP...) est comparé sans tenir compte des majuscules.
    La fenêtre de `window_seconds` part de la première tentative. Le cache Django garde le
    nombre de tentatives et le début de la fenêtre, avec le délai restant comme durée de vie :
    la fenêtre a la même durée quel que soit le cache (base de données en production, mémoire en test).
    Le comptage lit puis écrit (le cache n'a pas d'incrément atomique) : deux essais simultanés peuvent
    compter pour un. La connexion compte l'essai avant la vérification lente du mot de passe.
    """

    name: str
    max_attempts: int
    window_seconds: int

    @property
    def window_text(self) -> str:
        """Durée de la fenêtre pour les messages : « 15 minutes », « une heure »."""
        return duration_text(timedelta(seconds=self.window_seconds))

    def _key(self, identifier: str) -> str:
        return f"{self.name}:{identifier.strip().lower()}"

    def _current(self, key: str) -> tuple[int, float]:
        """Tentatives comptées et début de la fenêtre ; (0, maintenant) si aucune fenêtre n'est en cours."""
        now = time.time()
        value = cache.get(key)
        if not isinstance(value, tuple) or now - value[1] >= self.window_seconds:
            return 0, now
        return value

    def _store(self, key: str, count: int, started: float) -> None:
        # Délai restant donné à chaque écriture : la fin de la fenêtre ne bouge pas.
        remaining = started + self.window_seconds - time.time()
        cache.set(key, (count, started), max(1, math.ceil(remaining)))

    def is_locked(self, identifier: str) -> bool:
        count, _ = self._current(self._key(identifier))
        return count >= self.max_attempts

    def record(self, identifier: str) -> None:
        key = self._key(identifier)
        count, started = self._current(key)
        self._store(key, count + 1, started)

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


# Connexion : par adresse e-mail depuis une même IP (seuil bas, sans bloquer le titulaire qui se
# connecte d'ailleurs), et par adresse e-mail toutes IP confondues (seuil haut, contre une attaque
# répartie sur de nombreuses IP). Une réinitialisation du mot de passe remet les deux à zéro.
login_failures = Limiter("login-failures", max_attempts=5, window_seconds=15 * 60)
login_failures_by_account = Limiter("login-failures-account", max_attempts=50, window_seconds=15 * 60)

# Par adresse e-mail.
password_reset_requests = Limiter("password-reset", max_attempts=3, window_seconds=60 * 60)
confirmation_emails = Limiter("sign-up-emails", max_attempts=3, window_seconds=60 * 60)

# Par compte connecté : ressaisie du mot de passe (changement d'e-mail ou de mot de passe,
# suppression du compte). Empêche de le deviner depuis une session volée.
password_confirmations = Limiter("password-confirmations", max_attempts=5, window_seconds=15 * 60)
# Par compte connecté : demandes de changement d'adresse (chacune envoie un e-mail à une adresse
# choisie par le client) ; on ne peut pas se servir du site pour écrire en masse à des tiers.
email_change_requests = Limiter("email-change", max_attempts=3, window_seconds=60 * 60)
# Par client : codes promo faux (essais au hasard).
wrong_promo_codes = Limiter("promo-codes", max_attempts=10, window_seconds=60 * 60)

# Par adresse IP : seuils larges, car un bureau ou un wifi partage souvent une même IP.
login_failures_by_ip = Limiter("login-failures-ip", max_attempts=20, window_seconds=15 * 60)
sign_ups_by_ip = Limiter("sign-ups-ip", max_attempts=5, window_seconds=60 * 60)
password_reset_requests_by_ip = Limiter("password-reset-ip", max_attempts=10, window_seconds=60 * 60)
confirmation_requests_by_ip = Limiter("confirmation-resend-ip", max_attempts=10, window_seconds=60 * 60)
email_change_requests_by_ip = Limiter("email-change-ip", max_attempts=10, window_seconds=60 * 60)
# Empêche de contourner la limite des codes promo en changeant de compte.
wrong_promo_codes_by_ip = Limiter("promo-codes-ip", max_attempts=30, window_seconds=60 * 60)

# Après une inscription, se connecter avec le mot de passe choisi révèle si l'adresse avait
# déjà un compte confirmé (la connexion échoue). Pour freiner ce test d'adresses en série :
# une IP qui s'est inscrite dans l'heure est bloquée 15 minutes après 3 échecs de connexion.
# `recent_sign_ups_by_ip` est remis à zéro à chaque inscription : l'heure part de la dernière.
recent_sign_ups_by_ip = Limiter("recent-sign-up-ip", max_attempts=1, window_seconds=60 * 60)
login_failures_after_sign_up_by_ip = Limiter(
    "login-failures-after-sign-up-ip", max_attempts=3, window_seconds=15 * 60
)


def login_key(email: str, ip: str) -> str:
    """Identifiant de `login_failures` : l'adresse e-mail et l'IP d'où viennent les essais."""
    return f"{email}|{ip}"


def unlock_login(email: str, ip: str) -> None:
    """Après une réinitialisation du mot de passe : la connexion redevient possible depuis cette IP."""
    login_failures.reset(login_key(email, ip))
    login_failures_by_account.reset(email)
