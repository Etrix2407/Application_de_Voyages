from importlib import import_module

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = "reviews"
    verbose_name = "avis clients"

    def ready(self):
        # Branche le retrait de l'avis quand le voyage est annulé, et l'effacement RGPD
        # des signatures à la suppression d'un compte.
        import_module("reviews.signals")
        # Déclare la reconstruction des e-mails des avis (nouvelles tentatives, renvoi manuel).
        import_module("reviews.services.email_rebuilders")
