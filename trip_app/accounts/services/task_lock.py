"""Verrou des tâches planifiées : un seul passage d'une même tâche à la fois (ex. process_emails).

Le verrou est une ligne en base (TaskLock), prise par une mise à jour conditionnelle : deux
passages lancés en même temps ne peuvent pas le prendre tous les deux. Il expire de lui-même,
pour qu'un passage interrompu (serveur arrêté) ne bloque pas les suivants.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from django.utils import timezone

from accounts.models import TaskLock


@contextmanager
def task_lock(name: str, duration: timedelta) -> Iterator[bool]:
    """Prend le verrou `name` pour `duration` au plus ; donne True si le passage peut avoir lieu.

        with task_lock("process_emails", timedelta(minutes=30)) as acquired:
            if acquired: ...

    Le verrou est rendu à la sortie du bloc, sauf s'il a expiré et été repris entre-temps.
    """
    now = timezone.now()
    holder = uuid.uuid4().hex
    TaskLock.objects.get_or_create(name=name, defaults={"locked_until": now})
    acquired = bool(
        TaskLock.objects.filter(name=name, locked_until__lte=now).update(locked_until=now + duration, holder=holder)
    )
    try:
        yield acquired
    finally:
        if acquired:
            TaskLock.objects.filter(name=name, holder=holder).update(locked_until=timezone.now(), holder="")
