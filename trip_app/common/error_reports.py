"""Rapport d'erreur (erreur 500) envoyé aux adresses ADMINS, sans données personnelles."""

from django.views.debug import SafeExceptionReporterFilter


class PrivateExceptionReporterFilter(SafeExceptionReporterFilter):
    """Masque tous les champs envoyés par le visiteur et tous ses cookies.

    Django ne masque par défaut que les champs déclarés sensibles vue par vue : ici les formulaires
    reçoivent des mots de passe et le cookie de session suffit à prendre la main sur un compte.
    """

    def get_post_parameters(self, request):
        if request is None:
            return {}
        return {name: self.cleansed_substitute for name in request.POST}

    def get_safe_cookies(self, request):
        if request is None:
            return {}
        return {name: self.cleansed_substitute for name in request.COOKIES}
