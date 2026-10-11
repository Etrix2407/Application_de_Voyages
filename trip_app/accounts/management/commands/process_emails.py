"""Envoie les e-mails programmés, retente les e-mails en attente et efface le journal de plus d'un an.

À planifier toutes les 5 minutes. Un seul passage à la fois : si le précédent tourne encore,
celui-ci s'arrête sans rien faire (verrou de 30 minutes au plus, voir task_lock.py).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand

from accounts.services.email_retry import retry_due_emails
from accounts.services.privacy import purge_old_email_log
from accounts.services.task_lock import task_lock

# Plus long qu'un passage (20 minutes au plus, voir MAX_PASS_DURATION) ; un passage interrompu
# libère le verrou au plus tard au bout de ce délai.
LOCK_DURATION = timedelta(minutes=30)


class Command(BaseCommand):
    help = (
        "Envoie les e-mails promotionnels programmés, retente les e-mails en attente (5 puis 15 minutes) "
        "et efface le journal des e-mails de plus d'un an."
    )

    def handle(self, *args, **options):
        with task_lock("process_emails", LOCK_DURATION) as acquired:
            if not acquired:
                self.stdout.write("Un autre passage est en cours : rien n'a été fait.")
                return
            self.stdout.write(f"E-mails envoyés ou retentés : {retry_due_emails()}")
            self.stdout.write(f"Lignes du journal effacées (plus d'un an) : {purge_old_email_log()}")
