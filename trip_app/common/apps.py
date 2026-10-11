from django.apps import AppConfig
from django.db.backends.signals import connection_created


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        from common.db import register_sql_normalize

        # Fonction SQL de normalisation (accents, majuscules) : recherches du catalogue et des clients.
        connection_created.connect(register_sql_normalize, dispatch_uid="common.sql_normalize")
