"""Paramètres Django du projet trip_app."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Les tests ne dépendent jamais des réglages locaux : même résultat sur toutes les machines.
# Reconnu uniquement avec « python manage.py test » (pas avec un autre lanceur de tests).
TESTING = "test" in sys.argv[1:2]

# Réglages locaux et secrets : fichier .env à la racine du dépôt (modèle : .env.example).
# Il n'est jamais commité ; les vraies variables d'environnement restent prioritaires.
if not TESTING:
    load_dotenv(BASE_DIR.parent / ".env")


def env_str(name: str, default: str = "") -> str:
    """Valeur d'une variable d'environnement, sans espaces autour.

    Pendant les tests, l'environnement est ignoré : la valeur par défaut s'applique toujours.
    """
    if TESTING:
        return default
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    """Nombre entier lu dans l'environnement ; une valeur vide garde la valeur par défaut."""
    value = env_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(
            f"La variable d'environnement {name} doit être un nombre entier (valeur reçue : « {value} »)."
        ) from None


def env_bool(name: str, default: bool) -> bool:
    """Oui/non lu dans l'environnement : 1 = oui, 0 = non ; une valeur vide garde la valeur par défaut."""
    value = env_str(name)
    if not value:
        return default
    if value not in ("0", "1"):
        raise RuntimeError(f"La variable d'environnement {name} doit valoir 0 ou 1 (valeur reçue : « {value} »).")
    return value == "1"


# Nom affiché sur le site (titres, en-tête, pied de page).
SITE_NAME = "Horizons Lointains"

# Mode debug désactivé par défaut : un oubli en production ne l'active jamais.
# En développement, mettre DJANGO_DEBUG=1 dans le fichier .env (voir .env.example).
DEBUG = env_bool("DJANGO_DEBUG", default=TESTING)

# La clé secrète ne doit jamais être commitée : elle vient toujours de l'environnement,
# même en développement. Seuls les tests ont une valeur fixe, inutilisable ailleurs.
SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not TESTING:
        raise RuntimeError("La variable d'environnement DJANGO_SECRET_KEY est obligatoire.")
    SECRET_KEY = "cle-reservee-aux-tests-uniquement"

# Nombre de serveurs intermédiaires (proxy) de confiance devant le site : 0 en direct.
# Sert à retrouver la vraie IP des visiteurs pour les limites anti-abus.
NUM_PROXIES = env_int("DJANGO_NUM_PROXIES", 0)

ALLOWED_HOSTS = [host.strip() for host in env_str("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()]


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "common",
    "accounts",
    "catalog",
    "promotions",
    "orders",
    "reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.middleware.ContentSecurityPolicyMiddleware",
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
        # Chaque transaction (transaction.atomic) prend le verrou d'écriture dès son début : deux
        # enregistrements simultanés passent l'un après l'autre, et le second voit le premier.
        # Ex. la dernière utilisation d'une promotion, revérifiée à l'envoi de la demande, ne peut
        # pas être prise par deux clients. Sans ce réglage, SQLite pourrait refuser l'un des deux
        # avec l'erreur « database is locked ». Le second attend au plus 20 secondes (timeout).
        # Mode WAL : les lectures ne sont plus bloquées pendant une écriture. Il ajoute deux fichiers
        # à côté de la base (db.sqlite3-wal et db.sqlite3-shm), qui en font partie : à sauvegarder
        # avec elle (ou utiliser la commande .backup de sqlite3). Le dossier doit être local, pas un
        # partage réseau.
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL;",
        },
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
PASSWORD_PEPPER = env_str("DJANGO_PASSWORD_PEPPER")
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

# Cache des limites anti-abus : table « django_cache » de la base SQLite, partagée par tous les processus
# du serveur et conservée au redémarrage. À créer une fois par « python manage.py createcachetable ».
# Choisie plutôt que des fichiers sur disque : ceux-ci étaient tous parcourus à chaque écriture
# (lent avec beaucoup de compteurs) et pouvaient se bloquer entre processus sous Windows.
# Grande capacité : impossible de faire « oublier » un compteur en remplissant le cache.
# Les tests gardent un cache en mémoire, isolé.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
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
EMAIL_BACKEND = env_str("DJANGO_EMAIL_BACKEND") or "django.core.mail.backends.console.EmailBackend"
# Expéditeur et adresse des réponses (Recap 5). Une ligne vide dans .env garde l'expéditeur
# par défaut ; avec Outlook, l'expéditeur doit être l'adresse Outlook (voir .env.example).
DEFAULT_FROM_EMAIL = env_str("DJANGO_DEFAULT_FROM_EMAIL") or "Horizons Lointains <noreply@horizons-lointains.be>"
# En-tête Reply-To des e-mails ; vide = pas d'en-tête (les réponses vont à l'expéditeur).
EMAIL_REPLY_TO = env_str("DJANGO_EMAIL_REPLY_TO", "info@horizons-lointains.be")
EMAIL_HOST = env_str("DJANGO_EMAIL_HOST") or "localhost"
EMAIL_PORT = env_int("DJANGO_EMAIL_PORT", 587)
EMAIL_HOST_USER = env_str("DJANGO_EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env_str("DJANGO_EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
# Délai maximal d'attente du serveur SMTP, en secondes : un serveur lent ne bloque pas la page.
EMAIL_TIMEOUT = env_int("DJANGO_EMAIL_TIMEOUT", 10)
# Adresse commune du personnel qui reçoit l'alerte « Nouvelle demande de voyage » (Recap 5).
# Une ligne vide dans .env garde l'adresse par défaut.
RESERVATIONS_EMAIL = env_str("DJANGO_RESERVATIONS_EMAIL") or "reservations@horizons-lointains.be"

# Adresse du site (ex. https://horizons-lointains.be), pour les liens absolus des e-mails
# envoyés hors d'une requête (commandes planifiées) et pour le logo. Obligatoire en production :
# sans elle, les liens de ces e-mails (dont le lien de désinscription, obligatoire) seraient incomplets.
SITE_URL = (env_str("DJANGO_SITE_URL") or ("http://127.0.0.1:8000" if DEBUG else "")).rstrip("/")
if not SITE_URL and not DEBUG and not TESTING:
    raise RuntimeError("La variable d'environnement DJANGO_SITE_URL est obligatoire (ex. https://horizons-lointains.be).")
if SITE_URL and not SITE_URL.startswith(("http://", "https://")):
    raise RuntimeError("DJANGO_SITE_URL doit commencer par http:// ou https:// (ex. https://horizons-lointains.be).")

# Mise en page des e-mails : logo (chemin d'un fichier static, ex. « img/logo-email.png ») et
# coordonnées de l'agence, ajoutées sous la signature « L'équipe Horizons Lointains » (une ligne
# par élément). Vides tant qu'ils ne sont pas fournis : la mise en page ne les affiche pas.
EMAIL_LOGO_STATIC_PATH = ""
EMAIL_SIGNATURE_LINES: list[str] = []

# Mode test des e-mails (Recap 5) : il dépend uniquement de DJANGO_DEBUG. Actif par défaut avec
# DJANGO_DEBUG=1 (DJANGO_EMAIL_TEST_MODE=0 le désactive), toujours désactivé avec DJANGO_DEBUG=0.
# Avec DJANGO_EMAIL_TEST_RECIPIENT, tous les messages partent à cette adresse (l'adresse d'origine
# est ajoutée dans l'objet) ; sinon ils s'affichent dans le terminal, quel que soit DJANGO_EMAIL_BACKEND.
EMAIL_TEST_MODE = DEBUG and env_bool("DJANGO_EMAIL_TEST_MODE", True)
EMAIL_TEST_RECIPIENT = env_str("DJANGO_EMAIL_TEST_RECIPIENT")
if EMAIL_TEST_MODE and not EMAIL_TEST_RECIPIENT:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Journal : avertissements et erreurs affichés dans la sortie du serveur, y compris en production
# (sans ce réglage, Django n'y affiche pas les erreurs 500). Les pages introuvables (404) ne sont
# pas journalisées. Format sans données personnelles : date, niveau, origine et message.
# Facultatif : DJANGO_ADMINS (adresses séparées par des virgules) reçoit aussi chaque erreur 500
# par e-mail en production, envoyé depuis DEFAULT_FROM_EMAIL.
ADMINS = [(email, email) for email in (part.strip() for part in env_str("DJANGO_ADMINS").split(",")) if email]
SERVER_EMAIL = DEFAULT_FROM_EMAIL
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name} : {message}", "style": "{"},
    },
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "filters": ["require_debug_false"],
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        # Remplace la configuration par défaut de Django, qui n'affiche rien quand DEBUG vaut 0.
        "django": {"handlers": ["console", "mail_admins"], "level": "WARNING", "propagate": False},
        "django.request": {"level": "ERROR"},
    },
}
if TESTING:
    # Les erreurs provoquées exprès par les tests n'encombrent pas leur affichage.
    LOGGING["handlers"]["console"]["level"] = "CRITICAL"


# Sécurité en production (site servi en HTTPS).
if not DEBUG and not TESTING:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # HSTS : à activer seulement une fois le HTTPS validé (ex. 31536000 = 1 an).
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 0)
    # Seulement si tous les sous-domaines du site sont eux aussi en HTTPS.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
    if NUM_PROXIES:
        # Derrière un proxy qui gère le HTTPS, Django reçoit la requête en HTTP : l'en-tête
        # posé par le proxy indique l'origine HTTPS (liens des e-mails en https://, pas de
        # boucle de redirection). Le proxy doit toujours remplacer cet en-tête.
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
