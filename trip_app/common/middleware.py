"""Middleware partagés par toutes les applications."""

# Politique de sécurité du contenu : le navigateur ne charge que les fichiers du site lui-même
# (feuille de style, photos, images en data:), refuse tout script ou style écrit dans la page et
# interdit d'afficher le site dans un cadre d'un autre site. Les pages n'ont aucun script ni style
# en ligne : en ajouter un demanderait de modifier cette politique.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "img-src 'self' data:",
        "style-src 'self'",
        "script-src 'self'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "base-uri 'self'",
        "object-src 'none'",
    ]
)


class ContentSecurityPolicyMiddleware:
    """Ajoute l'en-tête Content-Security-Policy à chaque réponse."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response
