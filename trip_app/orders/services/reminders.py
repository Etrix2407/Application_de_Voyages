"""Rappel envoyé 7 jours avant le départ (v5) : passeport, visa, décalage horaire et monnaie.

Seulement pour une demande confirmée, dont le client a encore son compte. Le rappel part :
- chaque jour, par la commande planifiée send_trip_reminders, pour les départs dans 7 jours
  ou moins (rattrapage tant que le départ n'est pas passé) ;
- tout de suite, quand une demande est confirmée alors que le départ est dans 7 jours ou moins.
La date d'envoi, notée sur la demande, empêche tout doublon.
"""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from catalog.services.time_zones import BELGIUM, format_offset, offset_from_belgium
from orders.models import Order, Status

REMINDER_DAYS_BEFORE_DEPARTURE = 7
TEMPLATE = "orders/emails/departure_reminder.txt"


def due_departure_reminders():
    """Demandes confirmées dont le départ est dans 7 jours ou moins, sans rappel envoyé."""
    today = timezone.localdate()
    return Order.objects.filter(
        status=Status.CONFIRMED,
        client__isnull=False,
        departure_reminder_sent_at__isnull=True,
        departure_date__gte=today,
        departure_date__lte=today + timedelta(days=REMINDER_DAYS_BEFORE_DEPARTURE),
    )


def send_departure_reminders(order_pk: int | None = None) -> int:
    """Envoie les rappels dus (ou celui d'une seule demande) ; renvoie le nombre de rappels envoyés."""
    orders = due_departure_reminders().select_related("client", "destination__country")
    if order_pk is not None:
        orders = orders.filter(pk=order_pk)
    return sum(_send_reminder(order) for order in orders)


def departure_reminder_context(order: Order) -> dict:
    """Variables du rappel, lues sur la fiche pays au moment de l'envoi."""
    country = order.destination.country
    return {
        "order": order,
        "user": order.client,
        "passport_required": country.passport_required,
        "visa": country.get_visa_display(),
        # Fuseau non renseigné : la ligne du décalage horaire est omise.
        "time_offset": _offset_on(country.time_zone, order.departure_date) if country.time_zone else "",
        "currency": country.currency,
        "order_link": site_url(reverse("my_order_detail", kwargs={"pk": order.pk})),
    }


@transaction.atomic
def _send_reminder(order: Order) -> bool:
    # Marque d'abord la demande, sous condition : deux envois simultanés ne partent pas tous les deux.
    claimed = Order.objects.filter(pk=order.pk, departure_reminder_sent_at__isnull=True).update(
        departure_reminder_sent_at=timezone.now()
    )
    if not claimed:
        return False
    send_email(
        order.client.email,
        EmailKind.DEPARTURE_REMINDER,
        TEMPLATE,
        departure_reminder_context(order),
        user=order.client,
        order_number=order.pk,
    )
    return True


def _offset_on(zone_name: str, day) -> str:
    """Décalage avec la Belgique le jour donné (à midi), changements d'heure compris."""
    return format_offset(offset_from_belgium(zone_name, datetime.combine(day, time(12), BELGIUM)))
