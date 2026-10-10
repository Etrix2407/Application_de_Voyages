"""Réactions aux événements de connexion et de suppression des comptes, et signaux émis par les comptes."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import pre_delete
from django.dispatch import Signal, receiver

from accounts.services.privacy import erase_email_log_of

# Émis quand un client change d'adresse e-mail (argument : user), dans la même transaction.
# Les autres applications y réagissent sans que accounts dépende d'elles.
email_changed = Signal()

# Le personnel travaille souvent sur un poste partagé à l'agence : sa connexion expire
# après une journée de travail. Les clients gardent la durée par défaut (2 semaines).
STAFF_SESSION_AGE = timedelta(hours=8)


@receiver(user_logged_in, dispatch_uid="accounts.staff_session_age")
def shorten_staff_session(sender, request, user, **kwargs):
    if request is not None and user.is_staff_member:
        request.session.set_expiry(STAFF_SESSION_AGE)


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL, dispatch_uid="accounts.erase_email_log")
def erase_email_log_of_deleted_account(sender, instance, **kwargs):
    # Quel que soit le chemin de suppression (profil, personnel, purge), dans la même transaction.
    erase_email_log_of(instance)
