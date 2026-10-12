"""Mise en cache du tableau de pilotage : recalculé au plus une fois par heure et par période."""

from dataclasses import dataclass
from datetime import datetime

from django.core.cache import cache
from django.utils import timezone
from django.utils.text import slugify

from dashboard.services.periods import Period
from dashboard.services.pilotage import build_pilotage

CACHE_DURATION = 60 * 60  # secondes


@dataclass(frozen=True)
class PilotageSnapshot:
    sections: dict
    computed_at: datetime


def pilotage_snapshot(period: Period) -> PilotageSnapshot:
    # Le libellé fait partie de la clé : mêmes dates mais autre comparaison (mois civil ou jour pour jour)
    # ou autre titre (« cette année » et « les 12 derniers mois » en décembre).
    key = f"dashboard:pilotage:{period.basis}:{period.start}:{period.end}:{slugify(period.label)}"
    snapshot = cache.get(key)
    if snapshot is None:
        snapshot = PilotageSnapshot(build_pilotage(period), timezone.now())
        cache.set(key, snapshot, CACHE_DURATION)
    return snapshot
