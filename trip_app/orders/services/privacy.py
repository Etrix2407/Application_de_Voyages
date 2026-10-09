"""RGPD : demandes de voyage d'un client qui supprime son compte."""

from orders.models import Order, StatusChange


def anonymize_orders_of(client) -> int:
    """Conserve les demandes pour les statistiques, mais efface leur texte libre.

    Les remarques et les motifs peuvent contenir des données personnelles (santé,
    situation familiale…). Restent : destination, dates, voyageurs, activités, prix,
    états et dates de l'historique. Le lien vers le client est retiré par la base
    (suppression du compte : client vide).
    """
    orders = Order.objects.filter(client=client)
    StatusChange.objects.filter(order__in=orders).update(reason="")
    return orders.update(remarks="")
