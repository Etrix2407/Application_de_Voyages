from importlib import import_module

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        # Branche la durée de connexion réduite du personnel et l'effacement RGPD du journal des e-mails.
        import_module("accounts.signals")
        # Déclare les types et les textes d'origine des e-mails des comptes (registre de tous les e-mails).
        import_module("accounts.services.email_texts")
        # Déclare la reconstruction des e-mails des comptes (nouvelles tentatives, renvoi manuel).
        import_module("accounts.services.email_rebuilders")
