"""Historique des promotions : chaque création, modification et désactivation."""

from promotions.models import Promotion, PromotionChange


def record(promotion: Promotion, action: str, author, details: str = "") -> PromotionChange:
    """Note l'action avec la date et le nom de son auteur (copie figée)."""
    return PromotionChange.objects.create(
        promotion=promotion, action=action, author=author, author_name=author.get_full_name(), details=details
    )
