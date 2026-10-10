"""Rappels de voyage (à planifier chaque jour) : rappel avant le départ et invitation à donner un avis.

Dans l'application reviews, la dernière : elle peut utiliser à la fois orders et reviews.
"""

from django.core.management.base import BaseCommand

from orders.services.reminders import send_departure_reminders
from reviews.services.invitations import send_review_invitations


class Command(BaseCommand):
    help = (
        "Envoie le rappel des départs dans 7 jours ou moins et l'invitation à donner un avis "
        "après le retour (chaque e-mail une seule fois par demande)."
    )

    def handle(self, *args, **options):
        reminders = send_departure_reminders()
        invitations = send_review_invitations()
        self.stdout.write(f"Rappels avant le départ envoyés : {reminders}")
        self.stdout.write(f"Invitations à donner un avis envoyées : {invitations}")
