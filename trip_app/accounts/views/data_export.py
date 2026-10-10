"""RGPD (droit à la portabilité) : l'utilisateur télécharge ses données dans un fichier JSON.

Chaque application fournit ses propres données (services data_export) : la vue les
assemble, comme le permet l'ordre des dépendances entre applications (voir README).
Le personnel n'a que son profil et ses e-mails : ni demandes, ni avis, ni favoris.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from accounts.services.data_export import emails_data, profile_data
from catalog.services.data_export import favorites_data
from orders.services.data_export import orders_data
from reviews.services.data_export import reviews_data

FILE_NAME = "donnees-horizons-lointains.json"


@login_required
def download_my_data(request):
    """Lecture seule (GET), comme toute page qui ne modifie rien ; chacun ne voit que ses données."""
    user = request.user
    data = {"profile": profile_data(user), "emails": emails_data(user)}
    if user.is_client:
        data.update(
            {
                "orders": orders_data(user),
                "reviews": reviews_data(user),
                "favorites": favorites_data(user),
            }
        )
    response = JsonResponse(data, json_dumps_params={"ensure_ascii": False, "indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{FILE_NAME}"'
    return response
