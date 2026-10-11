"""Rappel envoyé 7 jours avant le départ (v5) : passeport, visa, décalage horaire et monnaie.

Seulement pour une demande confirmée, dont le client a encore son compte. Le rappel part :
- chaque jour, par la commande planifiée send_trip_reminders, pour les départs dans 7 jours
  ou moins (rattrapage tant que le départ n'est pas passé) ;
- tout de suite, quand une demande est confirmée alors que le départ est dans 7 jours ou moins.
La date d'envoi, notée sur la demande, empêche tout doublon.
"""

from datetime import timedelta

from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from accounts.models import EmailKind
from accounts.services.emails import send_email, site_url
from catalog.services.time_zones import format_offset, offset_on
from orders.models import Order, Status
from orders.services.labels import destination_label

REMINDER_DAYS_BEFORE_DEPARTURE = 7


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
    """Champs du rappel, lus sur la fiche pays au moment de l'envoi."""
    country = order.destination.country
    if country.passport_required:
        identity = "Un passeport valide est obligatoire pour ce pays."
    else:
        identity = "Une carte d'identité valide suffit pour ce pays."
    # Fuseau non renseigné : la ligne du décalage horaire est omise.
    time_offset = ""
    if country.time_zone:
        time_offset = f"- Décalage horaire le jour du départ : {format_offset(offset_on(country.time_zone, order.departure_date))}"
    return {
        "prénom": order.client.first_name,
        "destination": destination_label(order),
        "date de départ": date_format(order.departure_date, "j F Y"),
        "date de retour": date_format(order.return_date, "j F Y"),
        "numéro": order.pk,
        "pièce d'identité": identity,
        "visa": country.get_visa_display(),
        "décalage horaire": time_offset,
        "monnaie": country.currency,
        "lien": site_url(reverse("my_order_detail", kwargs={"pk": order.pk})),
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
        departure_reminder_context(order),
        user=order.client,
        order_number=order.pk,
    )
    return True
