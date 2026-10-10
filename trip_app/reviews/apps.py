from importlib import import_module

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reviews"
    verbose_name = "avis clients"

    def ready(self):
        # Branche le retrait de l'avis quand le voyage est annulé, et l'effacement RGPD
        # des signatures à la suppression d'un compte.
        import_module("reviews.signals")
