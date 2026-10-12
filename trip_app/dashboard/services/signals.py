"""Signaux du tableau de pilotage : indicateurs hors des seuils fixés par l'administrateur (Recap 6).

- Évalués à chaque affichage, à partir des chiffres en cache (dashboard.services.cache) et des seuils
  en vigueur : ils ne sont pas mis en cache, un seuil modifié s'applique tout de suite.
- « Dépasse » = strictement supérieur, « passe sous » = strictement inférieur : un indicateur égal
  au seuil ne donne pas de signal.
- Taux absent (None : aucune commande, ou aucune commande traitée) : pas de signal.
- Les taux sont affichés au dixième (« 25,1 % ») : arrondis à l'unité comme les gros chiffres,
  un taux juste au-dessus du seuil s'afficherait égal au seuil.
- Aucun e-mail n'est envoyé.
"""

from decimal import Decimal

from common.text import NBSP
from dashboard.models import SignalThresholds
from dashboard.services.orders_section import OrdersSection


def active_signals(orders: OrdersSection, thresholds: SignalThresholds) -> list[str]:
    """Texte de chaque signal actif, ex. « Taux d'annulation : 31 % (seuil : 25 %) »."""
    signals = []
    cancellation = orders.cancellation_rate
    if cancellation is not None and cancellation > thresholds.max_cancellation_rate:
        signals.append(
            f"Taux d'annulation : {_rate_text(cancellation)} (seuil : {thresholds.max_cancellation_rate}{NBSP}%)"
        )
    if orders.overdue_pending_count > thresholds.max_overdue_pending:
        signals.append(
            f"Commandes en attente depuis plus de 48 h : {orders.overdue_pending_count} "
            f"(seuil : {thresholds.max_overdue_pending})"
        )
    processed = orders.processed_within_48h_rate
    if processed is not None and processed < thresholds.min_processed_within_48h_rate:
        signals.append(
            f"Commandes traitées en moins de 48 h : {_rate_text(processed)} "
            f"(seuil : {thresholds.min_processed_within_48h_rate}{NBSP}%)"
        )
    return signals


def _rate_text(rate: Decimal) -> str:
    """« 25,1 % », ou « 31 % » pour un taux rond."""
    text = f"{rate:.1f}".removesuffix(".0").replace(".", ",")
    return f"{text}{NBSP}%"
