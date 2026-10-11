"""Textes des e-mails (v5) : registre des types, texte d'origine de chaque type, champs variables et
texte de l'administrateur.

Chaque application déclare ses types d'e-mails, avec le texte d'origine de chacun, par
register_email_kinds, dans un module importé par le ready() de l'application : les comptes ici
même (AccountEmail), les autres dans leur services/email_texts.py (OrderEmail, ReviewEmail,
PromotionEmail). accounts ne connaît donc pas les e-mails des autres applications, et un nouveau
type ne demande aucune migration (EmailLog.kind et EmailText.kind n'ont pas de choices).

L'administrateur peut remplacer l'objet et le texte d'un type d'e-mail (modèle EmailText), mais pas
la mise en page (emails/base.html, signature, logo) ni les champs variables. Un champ s'écrit entre
accolades, ex. {prénom}, et il est rempli au moment de l'envoi. Les parties calculées (récapitulatif
d'une demande, lignes facultatives, bloc de l'offre...) forment chacune un seul champ : l'administrateur
ne voit jamais de syntaxe de gabarit.

DEFAULT_TEXTS est la seule source des textes d'origine : sans texte de l'administrateur, c'est lui
qui est utilisé. Chaque appelant de send_email fournit la valeur de tous les champs de son type.

Version HTML : tout est échappé et rien n'est rendu cliquable automatiquement (un prénom ou un avis
qui contient une adresse web ne devient jamais un lien, pas plus qu'une adresse écrite par
l'administrateur). Seuls les champs de type lien, déclarés dans DefaultText.links, deviennent un
bouton au texte explicite ; la version texte garde l'adresse complète.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import NamedTuple

from django.core.exceptions import ImproperlyConfigured
from django.db.models import TextChoices
from django.utils.html import escape, linebreaks
from django.utils.safestring import SafeString, mark_safe

from accounts.models import AccountEmail, EmailText

# Champ variable : un nom entre accolades, sans accolade à l'intérieur.
FIELD = re.compile(r"\{([^{}]*)\}")


@dataclass(frozen=True)
class DefaultText:
    """Texte d'origine d'un type d'e-mail. `fields` : nom de chaque champ variable → description.

    `links` : champs de type lien → texte du bouton dans la version HTML. La valeur d'un tel champ
    finit par l'adresse, seule sur sa dernière ligne (une phrase peut la précéder).
    """

    subject: str
    body: str
    fields: dict[str, str]
    links: dict[str, str] = field(default_factory=dict)


class RenderedEmail(NamedTuple):
    """Objet, version texte et corps de la version HTML (placé dans emails/base.html)."""

    subject: str
    text: str
    html: SafeString


# Registre des types d'e-mails, rempli au démarrage par register_email_kinds, dans l'ordre de
# déclaration : le type (avec son libellé) et le texte d'origine de chaque valeur.
_KINDS: dict[str, TextChoices] = {}
DEFAULT_TEXTS: dict[str, DefaultText] = {}


def register_email_kinds(kinds: type[TextChoices], texts: Mapping[str, DefaultText]) -> None:
    """Déclare les types d'e-mails d'une application et le texte d'origine de chacun.

    `kinds` : valeur de chaque type (stockée au journal, elle ne change jamais) et libellé affiché
    au personnel. À appeler au démarrage, dans un module importé par le ready() de l'application :
    les types s'affichent dans cet ordre sur la page « Modèles des e-mails ».
    """
    if set(texts) != set(kinds):
        raise ImproperlyConfigured(f"{kinds.__name__} : il faut un texte d'origine par type d'e-mail.")
    # La valeur est la clé du journal : deux applications ne peuvent pas déclarer la même.
    already_declared = [kind.value for kind in kinds if kind.value in _KINDS]
    if already_declared:
        raise ImproperlyConfigured(f"Type d'e-mail déclaré deux fois : {', '.join(already_declared)}.")
    for kind in kinds:
        _KINDS[kind.value] = kind
        DEFAULT_TEXTS[kind.value] = texts[kind]


def email_kinds() -> list[TextChoices]:
    """Tous les types déclarés, dans l'ordre de déclaration (applications dans l'ordre de INSTALLED_APPS)."""
    return list(_KINDS.values())


def find_email_kind(value: str) -> TextChoices | None:
    """Type déclaré sous cette valeur, ou None."""
    return _KINDS.get(value)


def email_kind_label(value: str) -> str:
    """Libellé d'un type ; sa valeur brute s'il n'est plus déclaré (ligne ancienne du journal)."""
    kind = _KINDS.get(value)
    return kind.label if kind is not None else value


def paragraphs(*parts: str) -> str:
    """Texte d'origine écrit paragraphe par paragraphe."""
    return "\n\n".join(parts)


# Champ commun à presque tous les e-mails, de toutes les applications.
FIRST_NAME = {"prénom": "Prénom du destinataire."}

# Textes d'origine des e-mails des comptes.
EMPLOYEE_NUMBER = {"numéro d'employé": "Numéro d'employé du membre du personnel."}
LAST_MESSAGE = "Ce message est le dernier que vous recevrez de notre part."

ACCOUNT_TEXTS = {
    AccountEmail.SIGN_UP_CONFIRMATION: DefaultText(
        "Confirmez votre inscription",
        paragraphs(
            "Bonjour {prénom},",
            "Bienvenue chez Horizons Lointains, et merci pour votre inscription. Pour confirmer votre adresse "
            "e-mail, ouvrez ce lien (valable 48 heures) :",
            "{lien}",
            "Si vous n'êtes pas à l'origine de cette inscription, ignorez cet e-mail : l'adresse ne sera pas "
            "confirmée et le compte sera effacé au bout de 30 jours.",
        ),
        {**FIRST_NAME, "lien": "Lien de confirmation de l'adresse e-mail (valable 48 heures)."},
        links={"lien": "Confirmer mon adresse e-mail"},
    ),
    AccountEmail.SIGN_UP_EXISTING: DefaultText(
        "Tentative d'inscription avec votre adresse",
        paragraphs(
            "Bonjour {prénom},",
            "Quelqu'un vient de demander la création d'un compte avec votre adresse e-mail. Un compte existe "
            "déjà pour cette adresse : aucun nouveau compte n'a été créé.",
            "Si c'est vous, connectez-vous :\n{lien de connexion}",
            "Mot de passe oublié ? Choisissez-en un nouveau :\n{lien mot de passe oublié}",
            "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet e-mail.",
        ),
        {
            **FIRST_NAME,
            "lien de connexion": "Lien vers la page de connexion.",
            "lien mot de passe oublié": "Lien vers la page « Mot de passe oublié ».",
        },
        links={"lien de connexion": "Me connecter", "lien mot de passe oublié": "Choisir un nouveau mot de passe"},
    ),
    AccountEmail.EMAIL_CHANGE_CONFIRMATION: DefaultText(
        "Confirmez votre nouvelle adresse e-mail",
        paragraphs(
            "Bonjour {prénom},",
            "Vous avez demandé à utiliser cette adresse e-mail pour votre compte. Pour confirmer, ouvrez ce "
            "lien (valable 24 heures) :",
            "{lien}",
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : rien ne sera modifié.",
        ),
        {**FIRST_NAME, "lien": "Lien de confirmation de la nouvelle adresse (valable 24 heures)."},
        links={"lien": "Confirmer ma nouvelle adresse e-mail"},
    ),
    AccountEmail.EMAIL_CHANGE_NOTICE: DefaultText(
        "Demande de changement de votre adresse e-mail",
        paragraphs(
            "Bonjour {prénom},",
            "Une demande de changement de l'adresse e-mail de votre compte vient d'être faite. L'adresse ne "
            "changera que si la nouvelle adresse est confirmée.",
            "Si ce n'est pas vous, changez dès maintenant votre mot de passe depuis votre profil, ou utilisez "
            "« Mot de passe oublié ».",
        ),
        FIRST_NAME,
    ),
    AccountEmail.PASSWORD_RESET: DefaultText(
        "Changement de votre mot de passe",
        paragraphs(
            "Bonjour {prénom},",
            "Vous avez demandé à changer le mot de passe de votre compte.\n"
            "Pour choisir un nouveau mot de passe, ouvrez ce lien (valable 1 heure) :",
            "{lien}",
            "Si vous n'êtes pas à l'origine de cette demande, ignorez simplement cet e-mail : votre mot de "
            "passe ne changera pas.",
        ),
        {**FIRST_NAME, "lien": "Lien pour choisir un nouveau mot de passe (valable 1 heure)."},
        links={"lien": "Choisir un nouveau mot de passe"},
    ),
    AccountEmail.CLIENT_PASSWORD_LINK: DefaultText(
        "Changement de votre mot de passe",
        paragraphs(
            "Bonjour {prénom},",
            "Un agent de l'agence vous envoie un lien pour choisir un nouveau mot de passe.\n"
            "Ouvrez ce lien (valable 1 heure) :",
            "{lien}",
            "Si vous n'avez rien demandé, ignorez simplement cet e-mail : votre mot de passe ne changera pas.",
        ),
        {**FIRST_NAME, "lien": "Lien pour choisir un nouveau mot de passe (valable 1 heure)."},
        links={"lien": "Choisir un nouveau mot de passe"},
    ),
    AccountEmail.AGENT_ACTIVATION: DefaultText(
        "Activation de votre compte",
        paragraphs(
            "Bonjour {prénom},",
            "Un compte agent a été créé pour vous (numéro d'employé : {numéro d'employé}).\n"
            "Pour choisir votre mot de passe, ouvrez ce lien (valable 7 jours) :",
            "{lien}",
            "Si le lien a expiré, demandez à l'administrateur de vous en renvoyer un.",
        ),
        {**FIRST_NAME, **EMPLOYEE_NUMBER, "lien": "Lien pour choisir son mot de passe (valable 7 jours)."},
        links={"lien": "Choisir mon mot de passe"},
    ),
    AccountEmail.PASSWORD_CHANGED: DefaultText(
        "Votre mot de passe a été modifié",
        paragraphs(
            "Bonjour {prénom},",
            "Le mot de passe de votre compte vient d'être modifié.",
            "Si c'est bien vous, vous n'avez rien à faire.",
            "Si ce n'est pas vous, contactez-nous sans attendre en répondant à cet e-mail. Vous pouvez aussi "
            "choisir dès maintenant un nouveau mot de passe avec « Mot de passe oublié », sur la page de "
            "connexion.",
        ),
        FIRST_NAME,
    ),
    AccountEmail.ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        paragraphs(
            "Bonjour {prénom},",
            "Comme vous l'avez demandé, votre compte a été supprimé et vos données personnelles ont été effacées.",
            LAST_MESSAGE,
            "Merci de nous avoir fait confiance.",
        ),
        FIRST_NAME,
    ),
    AccountEmail.UNCONFIRMED_ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        paragraphs(
            "Bonjour {prénom},",
            "Un compte a été créé sur notre site avec cette adresse e-mail il y a plus de 30 jours, mais "
            "l'adresse n'a jamais été confirmée. Comme annoncé lors de l'inscription, ce compte a été supprimé "
            "et ses données ont été effacées.",
            "Si vous souhaitez voyager avec nous, vous pouvez créer un nouveau compte à tout moment.",
            LAST_MESSAGE,
        ),
        FIRST_NAME,
    ),
    AccountEmail.STAFF_ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        paragraphs(
            "Bonjour {prénom},",
            "Votre compte du personnel (numéro d'employé : {numéro d'employé}) a été supprimé par "
            "l'administrateur. Vous ne pouvez plus vous connecter au site.",
            LAST_MESSAGE,
        ),
        {**FIRST_NAME, **EMPLOYEE_NUMBER},
    ),
    AccountEmail.STAFF_PASSWORD_LINK: DefaultText(
        "Choisissez un nouveau mot de passe",
        paragraphs(
            "Bonjour {prénom},",
            "L'administrateur vous envoie un lien pour choisir un nouveau mot de passe pour votre compte du "
            "personnel (numéro d'employé : {numéro d'employé}).\nOuvrez ce lien (valable 7 jours) :",
            "{lien}",
            "Tant que vous n'utilisez pas ce lien, votre mot de passe actuel reste valable. Si le lien a expiré, "
            "demandez à l'administrateur de vous en renvoyer un.",
        ),
        {**FIRST_NAME, **EMPLOYEE_NUMBER, "lien": "Lien pour choisir un nouveau mot de passe (valable 7 jours)."},
        links={"lien": "Choisir un nouveau mot de passe"},
    ),
}

register_email_kinds(AccountEmail, ACCOUNT_TEXTS)


def current_text(kind: str) -> tuple[str, str]:
    """Objet et texte utilisés pour ce type : ceux de l'administrateur, sinon ceux d'origine."""
    custom = EmailText.objects.filter(kind=kind).first()
    if custom is not None:
        return custom.subject, custom.body
    default = DEFAULT_TEXTS[kind]
    return default.subject, default.body


def current_subject(kind: str) -> str:
    return current_text(kind)[0]


def render_email(
    kind: str, values: Mapping[str, object], text: tuple[str, str] | None = None
) -> RenderedEmail:
    """Objet, texte et corps HTML prêts à envoyer : le texte utilisé (voir current_text, ou `text`
    déjà lu par l'appelant), champs remplis."""
    subject, body = text if text is not None else current_text(kind)
    links = DEFAULT_TEXTS[kind].links

    def html_value(name: str, value: object) -> str:
        return _link_html(str(value), links[name]) if name in links else escape(value)

    html = linebreaks(_fill(body, values, escape, html_value), autoescape=False)
    return RenderedEmail(subject, fill_fields(body, values), mark_safe(html))


def fill_fields(text: str, values: Mapping[str, object]) -> str:
    """Remplace chaque {champ} par sa valeur.

    Une valeur n'est jamais relue : des accolades dans un prénom ou un message restent telles quelles.
    Un champ vide seul sur sa ligne (ligne facultative) fait disparaître la ligne, sans laisser
    deux lignes vides de suite. Un champ inconnu reste tel quel.
    """
    return _fill(text, values, str, lambda name, value: str(value))


# Champ de type lien : une phrase facultative, puis l'adresse seule sur la dernière ligne.
_TRAILING_URL = re.compile(r"(?:(.*)\n)?(https?://\S+)", re.DOTALL)

# Bouton lisible : texte blanc sur bleu foncé (contraste élevé), souligné pour rester repérable.
_BUTTON_STYLE = (
    "display: inline-block; padding: 12px 20px; background-color: #0b4f8a; color: #ffffff; "
    "font-weight: bold; text-decoration: underline; border-radius: 4px;"
)


def _link_html(value: str, label: str) -> str:
    """Champ de type lien en HTML : la phrase éventuelle, puis un bouton au texte explicite."""
    match = _TRAILING_URL.fullmatch(value.strip())
    if match is None:  # pas d'adresse (ex. « délai dépassé ») : simple texte
        return escape(value)
    intro, url = match.groups()
    button = f'<a href="{escape(url)}" style="{_BUTTON_STYLE}">{escape(label)}</a>'
    return f"{escape(intro)}\n{button}" if intro else button


def _fill(
    text: str,
    values: Mapping[str, object],
    literal: Callable[[str], str],
    value: Callable[[str, object], str],
) -> str:
    """Remplit les champs (voir fill_fields) ; `literal` transforme le texte fixe, `value` chaque valeur."""

    def fill_line(line: str) -> str:
        # FIELD.split alterne texte fixe (rangs pairs) et nom de champ (rangs impairs).
        parts = FIELD.split(line)
        return "".join(
            literal(part) if index % 2 == 0
            else value(part, values[part]) if part in values
            else literal(f"{{{part}}}")
            for index, part in enumerate(parts)
        )

    kept: list[str] = []
    drop_blank_line = False
    for line in text.split("\n"):
        alone = FIELD.fullmatch(line.strip())
        if alone and str(values.get(alone[1], "-")) == "":
            drop_blank_line = not kept or kept[-1].strip() == ""
            continue
        if drop_blank_line and not line.strip():
            drop_blank_line = False
            continue
        drop_blank_line = False
        kept.append(fill_line(line))
    return "\n".join(kept)


def fields_in(text: str) -> list[str]:
    """Noms des champs écrits dans le texte, dans l'ordre."""
    return FIELD.findall(text)


def has_lone_brace(text: str) -> bool:
    """Accolade ouvrante ou fermante qui n'entoure pas un nom de champ."""
    rest = FIELD.sub("", text)
    return "{" in rest or "}" in rest
