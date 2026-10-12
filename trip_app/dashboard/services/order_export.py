"""Export des commandes d'une période en CSV, avec sa trace au journal (administrateur).

Choix du format : « Excel ou CSV » sans bibliothèque supplémentaire, donc un CSV qu'Excel
ouvre directement en français : UTF-8 avec BOM (accents lus correctement), séparateur « ; »,
décimales avec une virgule, dates JJ/MM/AAAA.

RGPD : ni nom ni coordonnées, seulement le numéro du client (vide si le compte a été supprimé) ;
aucune remarque libre, qui pourrait contenir des données personnelles.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from dashboard.models import ExportLog
from dashboard.services.order_figures import latest_discount, latest_price
from dashboard.services.periods import Period
from orders.models import Order, OrderStatus

HEADERS = [
    "Numéro",
    "Date de commande",
    "Date de départ",
    "Destination",
    "Pays",
    "Numéro de client",
    "Voyageurs",
    "Montant estimé (€)",
    "Remise (€)",
    "État",
]

# Une cellule qui commence par l'un de ces caractères serait lue comme une formule par Excel.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class OrderExport:
    content: str
    file_name: str
    row_count: int


def export_orders(period: Period, author: User) -> OrderExport:
    """Prépare le fichier et enregistre sa trace dans la même transaction."""
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM : Excel reconnaît l'UTF-8.
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(HEADERS)
    row_count = 0
    with transaction.atomic():
        for order in _orders(period).iterator():
            writer.writerow([_cell(value) for value in _row(order)])
            row_count += 1
        ExportLog.objects.create(
            author=author,
            author_name=author.get_full_name(),
            start=period.start,
            end=period.end,
            basis=period.basis,
            row_count=row_count,
        )
    return OrderExport(buffer.getvalue(), f"commandes_{period.start}_{period.end}.csv", row_count)


def _orders(period: Period):
    # Seulement les colonnes exportées (values) : ni nom, ni e-mail, ni remarques ne sont lus.
    return (
        period.filter_orders(Order.objects.all())
        .annotate(travellers=F("adults") + F("children"), amount=latest_price(), retained_discount=latest_discount())
        .order_by("created_at", "pk")
        .values(
            "pk",
            "created_at",
            "departure_date",
            "destination_name",
            "country_name",
            "client_id",
            "travellers",
            "amount",
            "retained_discount",
            "status",
        )
    )


def _row(order: dict) -> list:
    return [
        order["pk"],
        timezone.localtime(order["created_at"]),
        order["departure_date"],
        order["destination_name"],
        order["country_name"],
        order["client_id"] or "",  # Vide : compte supprimé, commande anonymisée.
        order["travellers"],
        order["amount"],
        order["retained_discount"],
        OrderStatus(order["status"]).label,
    ]


def _cell(value) -> str | int:
    """Format belge des dates et montants ; texte protégé contre l'injection de formules."""
    if isinstance(value, date):  # Date de départ, et date-heure de commande (datetime hérite de date).
        return value.strftime("%d/%m/%Y")
    if isinstance(value, Decimal):
        return f"{value:.2f}".replace(".", ",")
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value
