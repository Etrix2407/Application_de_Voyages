"""Désinscription des e-mails promotionnels par le lien reçu dans chaque message (sans connexion)."""

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from accounts.services.unsubscribe import client_from_token, unsubscribe


# Le jeton signé du lien authentifie la demande : pas de jeton CSRF exigé, ce qui permet aussi
# la désinscription directe depuis la messagerie (POST « List-Unsubscribe=One-Click », RFC 8058).
@csrf_exempt
def unsubscribe_from_promotions(request, token):
    """Ouvrir le lien ne désinscrit pas : un bouton le confirme (POST).

    Ainsi, les logiciels qui inspectent les liens des e-mails ne désinscrivent pas à la place du client.
    """
    user = client_from_token(token)
    if user is None:
        return render(request, "accounts/unsubscribe/invalid.html")
    if request.method == "POST":
        unsubscribe(user)
        return render(request, "accounts/unsubscribe/done.html")
    if not user.accepts_promotional_emails:
        return render(request, "accounts/unsubscribe/done.html")
    return render(request, "accounts/unsubscribe/confirm.html")
