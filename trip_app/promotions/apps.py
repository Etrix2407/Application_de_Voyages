from importlib import import_module

from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    name = "promotions"
    verbose_name = "promotions"

    def ready(self):
        # Déclare le type et le texte d'origine des e-mails promotionnels (modèles des e-mails).
        import_module("promotions.services.email_texts")
        # Déclare la construction des e-mails promotionnels (premier envoi, nouvelles tentatives, renvoi).
        import_module("promotions.services.email_rebuilders")
