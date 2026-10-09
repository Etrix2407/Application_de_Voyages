"""Favoris des clients : requêtes réutilisées par plusieurs pages."""

from catalog.models import Activity, Destination, FavoriteActivity, FavoriteDestination


def is_favorite(user, item: Destination | Activity) -> bool:
    """Pour afficher le bon bouton sur les pages de détail (clients uniquement)."""
    # Un visiteur (non connecté) n'a pas de favoris.
    if not user.is_authenticated or not user.is_client:
        return False
    if isinstance(item, Destination):
        return FavoriteDestination.objects.filter(client=user, destination=item).exists()
    return FavoriteActivity.objects.filter(client=user, activity=item).exists()
