"""Évolution d'un indicateur par rapport à la période précédente : « +12 % », « nouveau », « — ».

- Le sens dépend de l'indicateur : une hausse des commandes est bonne, une hausse des annulations mauvaise.
- Période précédente à zéro : pas de pourcentage (jamais de division par zéro).
- Arrondi à l'unité ; une évolution qui s'arrondit à 0 % est affichée comme une égalité.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from common.text import NBSP

GOOD, BAD, NEUTRAL = "good", "bad", "neutral"


@dataclass(frozen=True)
class Comparison:
    text: str
    tone: str
    # Flèche de la hausse ou de la baisse : le sens ne repose pas sur la seule couleur.
    arrow: str = ""
    # Vrai pour un pourcentage : il se lit avec « par rapport à … ».
    is_percentage: bool = False


def compare(current, previous, higher_is_better: bool = True) -> Comparison:
    """Compare deux valeurs (entiers, Decimal ou taux) ; aucune n'est négative."""
    if not previous:
        if not current:
            return Comparison("—", NEUTRAL)
        return Comparison("nouveau", GOOD if higher_is_better else BAD)
    # str() : un taux en float garde la valeur affichée (0.1 et non 0.1000000000000000055…).
    change = (Decimal(str(current)) - Decimal(str(previous))) * 100 / Decimal(str(previous))
    percent = int(change.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if percent == 0:
        return Comparison(f"0{NBSP}%", NEUTRAL, is_percentage=True)
    rising = percent > 0
    tone = GOOD if rising == higher_is_better else BAD
    text = f"{'+' if rising else '-'}{abs(percent):,}{NBSP}%".replace(",", NBSP)
    return Comparison(text, tone, "▲" if rising else "▼", is_percentage=True)
