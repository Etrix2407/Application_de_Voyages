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


def current_offers(today=None, exclude=()) -> list[Promotion]:
    """Promotions automatiques en cours, de celle qui se termine le plus tôt à la plus tardive."""
    promotions = (
        Promotion.objects.running(today)
        .automatic()
        .exclude(pk__in=exclude)
        .prefetch_related(
            Prefetch("countries", queryset=Country.objects.visible().order_by("name")),
            Prefetch("destinations", queryset=Destination.objects.visible().order_by("name")),
        )
        .order_by("ends_on", "name", "pk")
    )
    return [promotion for promotion in promotions if promotion.scope == Scope.CATALOG or promotion.targets_label]


def targets(promotion: Promotion, destination: Destination) -> bool:
    """La destination est dans la portée (pays et destinations préchargés par current_offers)."""
    if promotion.scope == Scope.COUNTRIES:
        return any(country.pk == destination.country_id for country in promotion.countries.all())
    if promotion.scope == Scope.DESTINATIONS:
        return any(target.pk == destination.pk for target in promotion.destinations.all())
    return True


def offers_for(destination: Destination, offers: list[Promotion]) -> list[Promotion]:
    """Offres (current_offers) qui visent cette destination (bandeau de la fiche)."""
    return [promotion for promotion in offers if targets(promotion, destination)]


def mark_promoted(destinations, offers: list[Promotion]) -> list:
    """Ajoute `has_promotion` à chaque destination (étiquette « Promo » des cartes)."""
    destinations = list(destinations)
    for destination in destinations:
        destination.has_promotion = any(targets(promotion, destination) for promotion in offers)
    return destinations
