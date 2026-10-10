"""RGPD : avis d'un client qui supprime son compte."""

from reviews.models import Review


def erase_signatures_of(client) -> int:
    """Efface en base la signature (« Julie D. ») des avis du client.

    Les avis restent publiés et comptés, signés « Voyageur anonyme » : le lien vers le
    client est retiré par la base avec celui de la demande (client vide).
    """
    return Review.objects.filter(order__client=client).update(signature="")
