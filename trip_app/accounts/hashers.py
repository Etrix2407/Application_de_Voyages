"""Hachage des mots de passe avec un « poivre ».

Le sel (aléatoire, propre à chaque mot de passe) est stocké dans la base avec
l'empreinte. Le poivre est un secret commun gardé HORS de la base (fichier .env) :
une base volée seule ne permet donc aucune attaque sur les mots de passe.

Attention : perdre ou changer le poivre rend tous les mots de passe poivrés
inutilisables (les utilisateurs devront passer par « Mot de passe oublié »).
"""

import hashlib
import hmac

from django.conf import settings
from django.contrib.auth.hashers import PBKDF2PasswordHasher


class PepperedPBKDF2PasswordHasher(PBKDF2PasswordHasher):
    """PBKDF2-SHA256 appliqué au mot de passe préalablement combiné au poivre (HMAC-SHA256)."""

    algorithm = "pbkdf2_sha256_pepper"

    def encode(self, password, salt, iterations=None):
        # verify() rappelle encode() : le poivre est donc aussi appliqué à la vérification.
        peppered = hmac.new(settings.PASSWORD_PEPPER.encode(), password.encode(), hashlib.sha256).hexdigest()
        return super().encode(peppered, salt, iterations)
