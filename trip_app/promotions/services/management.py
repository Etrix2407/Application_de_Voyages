"""Gestion des promotions par l'administrateur : création, modification, désactivation, suppression.

Chaque action est notée dans l'historique. Pas de suppression en principe : on désactive.
Une promotion jamais utilisée peut être supprimée (celles déjà utilisées sont protégées
par les demandes de voyage qui les gardent).
"""

from django.db import transaction
from django.db.models import ProtectedError

from promotions.models import Action, Promotion
from promotions.services.history import record


class PromotionInUse(Exception):
    """La promotion a déjà été utilisée : elle se désactive, elle ne se supprime pas."""


@transaction.atomic
def create_promotion(form, author) -> Promotion:
    promotion = form.save()
    record(promotion, Action.CREATED, author)
    return promotion


@transaction.atomic
def update_promotion(form, author) -> Promotion:
    promotion = form.save()
    if form.changed_data:
        labels = [str(form.fields[name].label).lower() for name in form.changed_data]
        record(promotion, Action.UPDATED, author, "Champs modifiés : " + ", ".join(labels) + ".")
    return promotion


@transaction.atomic
def disable_promotion(promotion: Promotion, author) -> bool:
    """Désactive la promotion ; False si elle l'était déjà (deux clics ou deux administrateurs)."""
    if not Promotion.objects.filter(pk=promotion.pk, is_active=True).update(is_active=False):
        return False
    promotion.is_active = False
    record(promotion, Action.DISABLED, author)
    return True


def delete_promotion(promotion: Promotion) -> None:
    try:
        promotion.delete()
    except ProtectedError:
        raise PromotionInUse from None
