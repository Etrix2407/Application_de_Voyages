"""Modèles des e-mails : l'administrateur modifie l'objet et le texte de chaque type d'e-mail.

La mise en page (logo, signature) et les champs variables ne sont pas modifiables : voir
accounts/services/email_texts.py. « Rétablir le texte d'origine » supprime le texte modifié.
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required
from accounts.forms import EmailTextForm
from accounts.models import EmailKind, EmailText
from accounts.services.email_texts import DEFAULT_TEXTS


def _email_kind(value: str) -> EmailKind:
    try:
        return EmailKind(value)
    except ValueError:
        raise Http404 from None


@administrator_required
def email_text_list(request):
    custom_texts = {text.kind: text for text in EmailText.objects.all()}
    rows = []
    for kind in EmailKind:
        custom = custom_texts.get(kind)
        subject = custom.subject if custom else DEFAULT_TEXTS[kind].subject
        rows.append({"kind": kind, "subject": subject, "custom": custom})
    return render(request, "accounts/email_texts/list.html", {"rows": rows})


@administrator_required
def edit_email_text(request, kind):
    kind = _email_kind(kind)
    default = DEFAULT_TEXTS[kind]
    custom = EmailText.objects.filter(kind=kind).first()
    # Sans texte modifié, le formulaire part du texte d'origine.
    text = custom or EmailText(kind=kind, subject=default.subject, body=default.body)
    form = EmailTextForm(request.POST or None, instance=text)
    if request.method == "POST" and form.is_valid():
        text = form.save(commit=False)
        text.updated_at = timezone.now()
        text.updated_by = request.user
        text.updated_by_name = request.user.get_full_name()
        text.save()
        messages.success(request, f"Le texte de l'e-mail « {kind.label} » a été enregistré.")
        return redirect("email_text_list")
    fields = [(f"{{{name}}}", description) for name, description in default.fields.items()]
    context = {"form": form, "kind": kind, "fields": fields, "custom": custom}
    return render(request, "accounts/email_texts/edit.html", context)


@administrator_required
def reset_email_text(request, kind):
    """Page de confirmation (GET), puis suppression du texte modifié (POST) : l'action est irréversible."""
    kind = _email_kind(kind)
    custom = EmailText.objects.filter(kind=kind).first()
    if custom is None:
        messages.info(request, f"L'e-mail « {kind.label} » a déjà son texte d'origine.")
        return redirect("email_text_list")
    if request.method == "POST":
        custom.delete()
        messages.success(request, f"Le texte d'origine de l'e-mail « {kind.label} » est rétabli.")
        return redirect("email_text_list")
    return render(request, "accounts/email_texts/reset.html", {"kind": kind, "custom": custom})
