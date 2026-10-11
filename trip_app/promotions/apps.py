from importlib import import_module

from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "promotions"
    verbose_name = "promotions"

    def ready(self):
        # Déclare la construction des e-mails promotionnels (premier envoi, nouvelles tentatives, renvoi).
        import_module("promotions.services.email_rebuilders")
