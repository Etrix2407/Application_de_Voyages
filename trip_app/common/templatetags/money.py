"""Montants dans les gabarits : {{ prix|euros }} affiche « 1 234,50 € »."""

from django import template

from common.text import euros as format_euros

register = template.Library()


@register.filter
def euros(amount) -> str:
    return "" if amount is None or amount == "" else format_euros(amount)
