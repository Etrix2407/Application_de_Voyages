"""E-mails en échec : liste et renvoi manuel par le personnel (agents et administrateur)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.models import EmailKind, EmailLog, EmailStatus, User
from accounts.services.email_retry import NOT_REBUILDABLE, OBSOLETE, resend

FAILURES_PER_PAGE = 25

# Liens envoyés au personnel : leur renvoi relève de la gestion du personnel (administrateur).
ADMINISTRATOR_ONLY_KINDS = (EmailKind.AGENT_ACTIVATION, EmailKind.STAFF_PASSWORD_LINK)


def _failures():
    # Seuls les e-mails qu'on peut encore renvoyer sont listés : ni compte supprimé (sans
    # destinataire), ni message devenu sans objet ou impossible à refaire (restent au journal).
    return (
        EmailLog.objects.filter(status=EmailStatus.FAILED)
        .exclude(recipient="")
        .exclude(last_error__in=(OBSOLETE, NOT_REBUILDABLE))
        .select_related("user")
    )


def _can_resend(user: User, log: EmailLog) -> bool:
    return user.is_administrator or log.kind not in ADMINISTRATOR_ONLY_KINDS


@staff_required
def email_failure_list(request):
    page = Paginator(_failures(), FAILURES_PER_PAGE).get_page(request.GET.get("page"))
    for log in page.object_list:
        log.can_resend = _can_resend(request.user, log)
    return render(request, "accounts/email_failures/list.html", {"page": page})


@staff_required
@require_POST
def resend_email(request, pk):
    log = get_object_or_404(_failures(), pk=pk)
    if not _can_resend(request.user, log):
        raise PermissionDenied
    if resend(log):
        messages.success(request, f"L'e-mail « {log.subject} » a été renvoyé à {log.recipient}.")
    elif log.status == EmailStatus.PENDING:
        messages.error(
            request,
            "Le renvoi a échoué (problème de messagerie). "
            "De nouvelles tentatives auront lieu automatiquement dans 5 puis 15 minutes.",
        )
    else:
        messages.error(request, f"Cet e-mail ne peut pas être renvoyé : {log.last_error}")
    return redirect("email_failure_list")
