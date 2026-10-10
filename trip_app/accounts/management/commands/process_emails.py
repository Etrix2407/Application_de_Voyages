"""Retente les e-mails en attente et efface le journal de plus d'un an (à planifier toutes les 5 minutes)."""

from django.core.management.base import BaseCommand

from accounts.services.email_retry import retry_due_emails
from accounts.services.privacy import purge_old_email_log


class Command(BaseCommand):
    help = "Retente les e-mails en attente (5 puis 15 minutes) et efface le journal des e-mails de plus d'un an."

    def handle(self, *args, **options):
        self.stdout.write(f"E-mails retentés : {retry_due_emails()}")
        self.stdout.write(f"Lignes du journal effacées (plus d'un an) : {purge_old_email_log()}")
