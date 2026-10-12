"""Tableau de pilotage (administrateur) : toutes les sections, calculées pour une période.

Le résultat est mis en cache (voir dashboard.services.cache) : il ne contient que des valeurs simples
(nombres, textes, listes, dataclasses), jamais de QuerySet, qui serait recalculé à chaque lecture.
"""

from dashboard.services.periods import Period


def build_pilotage(period: Period) -> dict:
    # Une ligne par section, ajoutée chacune à la place de son repère.
    return {
        "period": period,
        "previous_period": period.previous(),

        # section: orders

        # section: rankings

        # section: charts

        # section: promotions_reviews

        # section: clients_emails
    }
