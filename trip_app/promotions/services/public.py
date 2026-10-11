"""Promotions montrées au public : bandeau, étiquette « Promo » et page « Nos offres du moment ».

- Seules les promotions automatiques en cours sont montrées : jamais les codes, ni les
  promotions désactivées, à venir ou terminées.
- Les pays et destinations visés sont limités à ceux qui sont proposés : un pays ou une
  destination désactivé n'est pas révélé, et une promotion qui ne vise plus rien de
  proposé n'est pas affichée.
- Une promotion dont le maximum au total est atteint n'est plus montrée : ce sont les demandes
  qui le disent, donc l'appelant passe `exclude` (voir orders.services.promotions.public_offers).
- Nombre fixe de requêtes, quel que soit le nombre de destinations ou de promotions.
"""

from django.db.models import Prefetch

from catalog.models import Country, Destination
from promotions.models import Promotion, Scope
from promotions.services.discounts import in_scope


def visible_targets(scope: str | None = None) -> list[Prefetch]:
    """Préchargement des pays et destinations visés, limité à ceux qui sont proposés.

    Avec ce préchargement, targets_label ne cite que des éléments proposés.
    `scope` : seulement la liste utile à cette portée (aucune pour tout le catalogue).
    """
    prefetches = {
        Scope.COUNTRIES: Prefetch("countries", queryset=Country.objects.visible().order_by("name")),
        Scope.DESTINATIONS: Prefetch("destinations", queryset=Destination.objects.visible().order_by("name")),
    }
    if scope is None:
        return list(prefetches.values())
    return [prefetches[scope]] if scope in prefetches else []


def offers_something(promotion: Promotion) -> bool:
    """La promotion vise encore quelque chose de proposé (cibles préchargées avec visible_targets)."""
    return promotion.scope == Scope.CATALOG or bool(promotion.targets_label)


def current_offers(today=None, exclude=()) -> list[Promotion]:
    """Promotions automatiques en cours, de celle qui se termine le plus tôt à la plus tardive."""
    promotions = (
        Promotion.objects.running(today)
        .automatic()
        .exclude(pk__in=exclude)
        .prefetch_related(*visible_targets())
        .order_by("ends_on", "name", "pk")
    )
    return [promotion for promotion in promotions if offers_something(promotion)]


def offers_for(destination: Destination, offers: list[Promotion]) -> list[Promotion]:
    """Offres (current_offers) qui visent cette destination (bandeau de la fiche)."""
    return [promotion for promotion in offers if in_scope(promotion, destination)]


def mark_promoted(destinations, offers: list[Promotion]) -> list:
    """Ajoute `has_promotion` à chaque destination (étiquette « Promo » des cartes)."""
    destinations = list(destinations)
    for destination in destinations:
        destination.has_promotion = any(in_scope(promotion, destination) for promotion in offers)
    return destinations
