"""E-mails en échec : liste et renvoi manuel par le personnel (agents et administrateur)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from accounts.models import NOT_RESENDABLE_FAILURES, AccountEmail, EmailLog, EmailStatus, User
from accounts.services.email_retry import RETRY_DELAYS, AlreadyResent, resend
from accounts.services.email_texts import email_kind_label
from common.text import duration_text

# « 5 minutes puis 15 minutes » : délais des nouvelles tentatives automatiques.
RETRY_TEXT = " puis ".join(duration_text(delay) for delay in RETRY_DELAYS.values())

FAILURES_PER_PAGE = 25

# Liens envoyés au personnel : leur renvoi relève de la gestion du personnel (administrateur).
ADMINISTRATOR_ONLY_KINDS = (AccountEmail.AGENT_ACTIVATION, AccountEmail.STAFF_PASSWORD_LINK)


def _failures():
    # Seuls les e-mails qu'on peut encore renvoyer sont listés : ni compte supprimé (sans
    # destinataire), ni message devenu sans objet ou impossible à refaire (restent au journal).
    return (
        EmailLog.objects.filter(status=EmailStatus.FAILED)
        .exclude(recipient="")
        .exclude(failure__in=NOT_RESENDABLE_FAILURES)
        .select_related("user")
    )


def _can_resend(user: User, log: EmailLog) -> bool:
    return user.is_administrator or log.kind not in ADMINISTRATOR_ONLY_KINDS


@staff_required
def email_failure_list(request):
    page = Paginator(_failures(), FAILURES_PER_PAGE).get_page(request.GET.get("page"))
    for log in page.object_list:
        log.can_resend = _can_resend(request.user, log)
        log.kind_label = email_kind_label(log.kind)
    return render(request, "accounts/email_failures/list.html", {"page": page})


@staff_required
@require_POST
def resend_email(request, pk):
    log = get_object_or_404(_failures(), pk=pk)
    if not _can_resend(request.user, log):
        raise PermissionDenied
    try:
        sent = resend(log)
    except AlreadyResent:
        messages.info(request, "Cet e-mail vient déjà d'être renvoyé : il n'a pas été envoyé une deuxième fois.")
        return redirect("email_failure_list")
    if sent:
        messages.success(request, f"L'e-mail « {log.subject} » a été renvoyé à {log.recipient}.")
    elif log.status == EmailStatus.PENDING:
        messages.error(
            request,
            "Le renvoi a échoué (problème de messagerie). "
            f"De nouvelles tentatives auront lieu automatiquement dans {RETRY_TEXT}.",
        )
    else:
        messages.error(request, f"Cet e-mail ne peut pas être renvoyé : {log.last_error}")
    return redirect("email_failure_list")
