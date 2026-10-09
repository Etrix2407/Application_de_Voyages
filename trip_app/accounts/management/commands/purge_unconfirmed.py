"""Supprime les inscriptions jamais confirmées depuis plus de 7 jours (à planifier chaque jour)."""

from django.core.management.base import BaseCommand

from accounts.services.sign_up import purge_unconfirmed


class Command(BaseCommand):
    help = "Supprime les inscriptions clients non confirmées depuis plus de 7 jours (RGPD)."

    def handle(self, *args, **options):
        deleted = purge_unconfirmed()
        self.stdout.write(f"Inscriptions non confirmées supprimées : {deleted}")
