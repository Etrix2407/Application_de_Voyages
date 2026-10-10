"""Réactions aux événements de connexion, et signaux émis par les comptes."""

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in
from django.dispatch import Signal, receiver

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
