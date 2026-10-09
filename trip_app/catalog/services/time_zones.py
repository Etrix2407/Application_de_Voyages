"""Fuseaux horaires des pays : décalage avec la Belgique calculé automatiquement.

L'agent choisit le fuseau principal du pays (ex. « Asie — Tokyo ») ; les décalages
en découlent, changements d'heure de la Belgique et du pays compris. La base des
fuseaux (IANA) est celle de Python (module zoneinfo, paquet tzdata sous Windows).
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from common.text import normalize

BELGIUM = ZoneInfo("Europe/Brussels")

# Régions de la base IANA, en français. Les autres noms (« Etc/GMT+3 », alias…) ne sont pas proposés.
REGIONS = {
    "Africa": "Afrique",
    "America": "Amérique",
    "Antarctica": "Antarctique",
    "Asia": "Asie",
    "Atlantic": "Atlantique",
    "Australia": "Australie",
    "Europe": "Europe",
    "Indian": "Océan Indien",
    "Pacific": "Pacifique",
}

# Jours de référence : milieu de l'été et de l'hiver belges.
SUMMER_DAY = (7, 15)
WINTER_DAY = (1, 15)


def format_offset(hours: Decimal) -> str:
    """Affiche un décalage horaire lisible : « +5 h 30 », « -6 h », « même heure »."""
    if not hours:
        return "même heure qu'en Belgique"
    sign = "+" if hours > 0 else "-"
    total_minutes = int(abs(hours) * 60)
    h, minutes = divmod(total_minutes, 60)
    return f"{sign}{h} h {minutes:02d}" if minutes else f"{sign}{h} h"


def time_zone_label(name: str) -> str:
    """« Asia/Tokyo » devient « Asie — Tokyo » ; « America/Argentina/Salta » : « Amérique — Argentina / Salta »."""
    region, _, place = name.partition("/")
    return f"{REGIONS.get(region, region)} — {place.replace('_', ' ').replace('/', ' / ')}"


@lru_cache(maxsize=1)
def time_zone_choices() -> list[tuple[str, str]]:
    """Fuseaux proposés à l'agent, triés par région puis par ville."""
    names = [name for name in available_timezones() if name.partition("/")[0] in REGIONS and "/" in name]
    return sorted(((name, time_zone_label(name)) for name in names), key=lambda choice: choice[1])


def is_known_time_zone(name: str) -> bool:
    return any(name == choice for choice, _ in time_zone_choices())


def time_zone_from_input(text: str) -> str | None:
    """Fuseau désigné par la saisie de l'agent, ou None s'il est introuvable ou ambigu.

    Accepte le libellé proposé (« Asie — Tokyo »), le nom technique (« Asia/Tokyo ») ou
    une ville seule (« tokyo »), sans tenir compte des majuscules ni des accents.
    """
    wanted = normalize(text)
    if not wanted:
        return None
    for name, label in time_zone_choices():
        if wanted in (normalize(label), normalize(name)):
            return name
    same_city = [name for name, label in time_zone_choices() if normalize(label.split(" — ", 1)[1]) == wanted]
    return same_city[0] if len(same_city) == 1 else None


def offset_from_belgium(zone_name: str, moment: datetime) -> Decimal:
    """Décalage, en heures, entre l'heure du pays et celle de la Belgique à cet instant."""
    difference = moment.astimezone(ZoneInfo(zone_name)).utcoffset() - moment.astimezone(BELGIUM).utcoffset()
    return Decimal(int(difference.total_seconds())) / 3600


@dataclass(frozen=True)
class TimeOffsets:
    summer: Decimal
    winter: Decimal
    today: Decimal

    @property
    def summer_display(self) -> str:
        return format_offset(self.summer)

    @property
    def winter_display(self) -> str:
        return format_offset(self.winter)

    @property
    def today_display(self) -> str:
        return format_offset(self.today)


def time_offsets(zone_name: str, today: date) -> TimeOffsets:
    """Décalages pendant l'été et l'hiver belges de l'année, et le jour donné (à midi)."""

    def at_noon(day: date) -> datetime:
        return datetime.combine(day, time(12), BELGIUM)

    return TimeOffsets(
        summer=offset_from_belgium(zone_name, at_noon(date(today.year, *SUMMER_DAY))),
        winter=offset_from_belgium(zone_name, at_noon(date(today.year, *WINTER_DAY))),
        today=offset_from_belgium(zone_name, at_noon(today)),
    )
