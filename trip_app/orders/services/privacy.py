"""RGPD : demandes de voyage d'un client qui supprime son compte."""

from orders.models import Order, Status, StatusChange
from orders.services.status import cancel_after_account_deletion


def anonymize_orders_of(client) -> int:
    """Conserve les demandes pour les statistiques, mais efface leur texte libre.

    Les remarques et les motifs peuvent contenir des données personnelles (santé,
    situation familiale…). Restent : destination, dates, voyageurs, activités, prix,
    états et dates de l'historique. Le lien vers le client est retiré par la base
    (suppression du compte : client vide). L'empreinte de l'adresse (client_fingerprint,
    HMAC, pas l'adresse en clair) est volontairement conservée : elle maintient la limite
    d'utilisation des promotions par client en cas de réinscription.
    Les demandes encore « En attente » sont ensuite annulées : il n'y a plus personne
    à rappeler. Leur motif d'annulation, fixé, ne contient aucune donnée personnelle.
    """
    orders = Order.objects.filter(client=client)
    StatusChange.objects.filter(order__in=orders).update(reason="")
    anonymized = orders.update(remarks="")
    for order in orders.filter(status=Status.PENDING):
        cancel_after_account_deletion(order)
    return anonymized
