"""Définitions communes aux chiffres des tableaux de bord, pour que toutes les sections comptent pareil.

Le délai de 48 h d'une demande en retard est défini avec les demandes (orders.models.OVERDUE_DELAY).

- Montant estimé d'une commande : le prix le plus récent (celui de la confirmation s'il existe,
  sinon l'estimation de départ), après remise, comme Order.latest_price. Ce n'est pas de l'argent encaissé.
- Remise : la plus récente, comme dans les statistiques d'une promotion.
"""

from django.db.models.functions import Coalesce


def latest_price():
    """Expression du montant estimé, à utiliser dans annotate() ou Sum()."""
    return Coalesce("confirmed_price", "estimated_price")


def latest_discount():
    """Expression de la remise retenue, à utiliser dans annotate() ou Sum()."""
    return Coalesce("confirmed_discount", "discount")
