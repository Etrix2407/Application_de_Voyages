"""Menu principal : signale le lien de la page affichée (aria-current), à l'écran et aux lecteurs d'écran."""

from django import template
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def current_page(context, url_name: str) -> str:
    """Attribut aria-current="page" si la page affichée est celle du lien, sinon rien."""
    request = context.get("request")
    if request is not None and request.path == reverse(url_name):
        return mark_safe(' aria-current="page"')
    return ""
