from importlib import import_module

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"
    verbose_name = "demandes de voyage"

    def ready(self):
        # Branche l'anonymisation RGPD des demandes à la suppression d'un compte.
        import_module("orders.signals")
