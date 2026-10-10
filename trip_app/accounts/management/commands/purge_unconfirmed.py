"""Supprime les comptes clients jamais confirmés depuis plus de 30 jours (à planifier chaque jour)."""

from django.core.management.base import BaseCommand

from accounts.services.sign_up import purge_unconfirmed


class Command(BaseCommand):
    help = "Supprime les comptes clients dont l'adresse n'a pas été confirmée en 30 jours (RGPD)."

    def handle(self, *args, **options):
        deleted = purge_unconfirmed()
        self.stdout.write(f"Comptes non confirmés supprimés : {deleted}")
