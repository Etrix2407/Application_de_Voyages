from importlib import import_module

from django.apps import AppConfig
from django.db.backends.signals import connection_created

from common.db import register_sql_normalize


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        # Branche la durée de connexion réduite du personnel et l'effacement RGPD du journal des e-mails.
        import_module("accounts.signals")
        # Déclare la reconstruction des e-mails des comptes (nouvelles tentatives, renvoi manuel).
        import_module("accounts.services.email_rebuilders")
        # Recherche de client sans accents faite par la base (voir matching_clients).
        connection_created.connect(register_sql_normalize, dispatch_uid="common.sql_normalize")
