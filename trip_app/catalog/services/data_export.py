"""RGPD (portabilité) : favoris d'un client, prêts à être exportés."""

from catalog.models import FavoriteActivity, FavoriteDestination


def favorites_data(client) -> dict:
    destinations = FavoriteDestination.objects.filter(client=client).select_related("destination__country")
    activities = FavoriteActivity.objects.filter(client=client).select_related("activity__country")
    return {
        "destinations": [
            {
                "name": favorite.destination.name,
                "country": favorite.destination.country.name,
                "added_at": favorite.added_at,
            }
            for favorite in destinations
        ],
        "activities": [
            {
                "name": favorite.activity.name,
                "country": favorite.activity.country.name,
                "added_at": favorite.added_at,
            }
            for favorite in activities
        ],
    }
