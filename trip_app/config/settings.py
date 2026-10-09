"""Paramètres Django du projet trip_app."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Les tests ne dépendent jamais des réglages locaux : même résultat sur toutes les machines.
TESTING = "test" in sys.argv[1:2]

# Réglages locaux et secrets : fichier .env à la racine du dépôt (modèle : .env.example).
# Il n'est jamais commité ; les vraies variables d'environnement restent prioritaires.
if not TESTING:
    load_dotenv(BASE_DIR.parent / ".env")

# Nom affiché sur le site (titres, en-tête, pied de page).
SITE_NAME = "Horizons Lointains"

# Mode debug désactivé par défaut : un oubli en production ne l'active jamais.
# En développement, mettre DJANGO_DEBUG=1 dans le fichier .env (voir .env.example).
DEBUG = os.environ.get("DJANGO_DEBUG", "1" if TESTING else "0") == "1"

# La clé secrète ne doit jamais être commitée : en production, elle vient de l'environnement.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("La variable d'environnement DJANGO_SECRET_KEY est obligatoire.")
    SECRET_KEY = "django-insecure-cle-de-developpement-uniquement"

# Nombre de serveurs intermédiaires (proxy) de confiance devant le site : 0 en direct.
# Sert à retrouver la vraie IP des visiteurs pour les limites anti-abus.
NUM_PROXIES = int(os.environ.get("DJANGO_NUM_PROXIES", "0"))

ALLOWED_HOSTS = [
    host for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host
]


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "catalog",
    "promotions",
    "orders",
    "reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.site",
                "reviews.context_processors.moderation_counter",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


AUTH_USER_MODEL = "accounts.User"

# Les mots de passe sont hachés (PBKDF2 par défaut) et doivent respecter ces règles.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "last_name", "first_name")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "accounts.validators.LetterAndDigitValidator"},
]

# « Poivre » : secret commun ajouté au hachage des mots de passe, gardé hors de la base.
# Obligatoire en production. Ne jamais le perdre ni le changer : tous les mots de passe
# deviendraient inutilisables (voir accounts/hashers.py).
PASSWORD_PEPPER = os.environ.get("DJANGO_PASSWORD_PEPPER", "")
if not PASSWORD_PEPPER and not DEBUG and not TESTING:
    raise RuntimeError("La variable d'environnement DJANGO_PASSWORD_PEPPER est obligatoire.")
if PASSWORD_PEPPER:
    PASSWORD_HASHERS = [
        "accounts.hashers.PepperedPBKDF2PasswordHasher",
        # Anciens mots de passe sans poivre : acceptés, puis convertis à la connexion suivante.
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    ]

# Pendant les tests uniquement : hachage rapide pour accélérer la suite (jamais en production).
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Cache des limites anti-abus : fichiers sur disque, partagés par tous les processus du
# serveur et conservés au redémarrage. Grande capacité : impossible de faire « oublier »
# un compteur en remplissant le cache. Les tests gardent un cache en mémoire, isolé.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "cache",
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    }
}
if TESTING:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


LANGUAGE_CODE = "fr-be"
TIME_ZONE = "Europe/Brussels"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Fichiers envoyés (photos des destinations). En production, à servir par le serveur web.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# Le lien « mot de passe oublié » est valable 1 heure.
PASSWORD_RESET_TIMEOUT = 60 * 60

# En développement, les e-mails s'affichent dans le terminal.
# En production : DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend et réglages SMTP.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "ne-pas-repondre@localhost")
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "1") == "1"


# Sécurité en production (site servi en HTTPS).
if not DEBUG and not TESTING:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    # HSTS : à activer seulement une fois le HTTPS validé (ex. 31536000 = 1 an).
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
    # Seulement si tous les sous-domaines du site sont eux aussi en HTTPS.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("DJANGO_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
    if NUM_PROXIES:
        # Derrière un proxy qui gère le HTTPS, Django reçoit la requête en HTTP : l'en-tête
        # posé par le proxy indique l'origine HTTPS (liens des e-mails en https://, pas de
        # boucle de redirection). Le proxy doit toujours remplacer cet en-tête.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
