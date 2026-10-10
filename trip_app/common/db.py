"""Fonction SQL de comparaison sans accents, pour filtrer dans la base plutôt qu'en Python."""

from django.db.models import CharField, Func

from common.text import normalize

SQL_NORMALIZE = "trip_normalize"


def register_sql_normalize(sender, connection, **kwargs):
    """SQLite ne sait pas ignorer les accents : on lui prête `normalize` à chaque connexion."""
    if connection.vendor == "sqlite":
        connection.connection.create_function(
            SQL_NORMALIZE, 1, lambda text: normalize(text or ""), deterministic=True
        )


class Normalize(Func):
    """Équivalent SQL de common.text.normalize (« Pérou » devient « perou »)."""

    function = SQL_NORMALIZE
    output_field = CharField()
