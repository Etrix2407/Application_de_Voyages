"""Réactions aux événements de connexion."""

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

# Le personnel travaille souvent sur un poste partagé à l'agence : sa connexion expire
# après une journée de travail. Les clients gardent la durée par défaut (2 semaines).
STAFF_SESSION_AGE = timedelta(hours=8)


@receiver(user_logged_in, dispatch_uid="accounts.staff_session_age")
def shorten_staff_session(sender, request, user, **kwargs):
    if request is not None and user.is_staff_member:
        request.session.set_expiry(STAFF_SESSION_AGE)
