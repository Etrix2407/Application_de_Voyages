"""Tableau de pilotage (administrateur) : toutes les sections, calculées pour une période.

Le résultat est mis en cache (voir dashboard.services.cache) : il ne contient que des valeurs simples
(nombres, textes, listes, dataclasses), jamais de QuerySet, qui serait recalculé à chaque lecture.
"""

from dashboard.services.charts import order_charts
from dashboard.services.orders_section import orders_section
from dashboard.services.periods import Period
from dashboard.services.promotions_reviews import promotions_reviews
from dashboard.services.rankings import build_rankings


def build_pilotage(period: Period) -> dict:
    # Une ligne par section, ajoutée chacune à la place de son repère.
    return {
        "period": period,
        "previous_period": period.previous(),

        "orders": orders_section(period),

        "rankings": build_rankings(period),

        "charts": order_charts(period),

        "promotions_reviews": promotions_reviews(period),

        # section: clients_emails
    }
