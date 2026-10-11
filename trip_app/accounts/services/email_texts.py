"""Textes des e-mails (v5) : texte d'origine de chaque type, champs variables et texte de l'administrateur.

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

from django.utils.html import escape, linebreaks
from django.utils.safestring import SafeString, mark_safe

from accounts.models import EmailKind, EmailText

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


def _paragraphs(*paragraphs: str) -> str:
    return "\n\n".join(paragraphs)


FIRST_NAME = {"prénom": "Prénom du destinataire."}
EMPLOYEE_NUMBER = {"numéro d'employé": "Numéro d'employé du membre du personnel."}
ORDER_NUMBER = {"numéro": "Numéro de la demande de voyage."}
DESTINATION = {"destination": "Destination et pays, par exemple « Kyoto (Japon) »."}
DATES = {"dates": "Dates du voyage, par exemple « du 3 mai 2026 au 13 mai 2026 »."}
REVIEW = {
    "titre": "Titre de l'avis.",
    "destination": "Destination et pays de l'avis, par exemple « Kyoto (Japon) ».",
}
LAST_MESSAGE = "Ce message est le dernier que vous recevrez de notre part."

DEFAULT_TEXTS: dict[str, DefaultText] = {
    EmailKind.SIGN_UP_CONFIRMATION: DefaultText(
        "Confirmez votre inscription",
        _paragraphs(
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
    EmailKind.SIGN_UP_EXISTING: DefaultText(
        "Tentative d'inscription avec votre adresse",
        _paragraphs(
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
    EmailKind.EMAIL_CHANGE_CONFIRMATION: DefaultText(
        "Confirmez votre nouvelle adresse e-mail",
        _paragraphs(
            "Bonjour {prénom},",
            "Vous avez demandé à utiliser cette adresse e-mail pour votre compte. Pour confirmer, ouvrez ce "
            "lien (valable 24 heures) :",
            "{lien}",
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail : rien ne sera modifié.",
        ),
        {**FIRST_NAME, "lien": "Lien de confirmation de la nouvelle adresse (valable 24 heures)."},
        links={"lien": "Confirmer ma nouvelle adresse e-mail"},
    ),
    EmailKind.EMAIL_CHANGE_NOTICE: DefaultText(
        "Demande de changement de votre adresse e-mail",
        _paragraphs(
            "Bonjour {prénom},",
            "Une demande de changement de l'adresse e-mail de votre compte vient d'être faite. L'adresse ne "
            "changera que si la nouvelle adresse est confirmée.",
            "Si ce n'est pas vous, changez dès maintenant votre mot de passe depuis votre profil, ou utilisez "
            "« Mot de passe oublié ».",
        ),
        FIRST_NAME,
    ),
    EmailKind.PASSWORD_RESET: DefaultText(
        "Changement de votre mot de passe",
        _paragraphs(
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
    EmailKind.CLIENT_PASSWORD_LINK: DefaultText(
        "Changement de votre mot de passe",
        _paragraphs(
            "Bonjour {prénom},",
            "Un agent de l'agence vous envoie un lien pour choisir un nouveau mot de passe.\n"
            "Ouvrez ce lien (valable 1 heure) :",
            "{lien}",
            "Si vous n'avez rien demandé, ignorez simplement cet e-mail : votre mot de passe ne changera pas.",
        ),
        {**FIRST_NAME, "lien": "Lien pour choisir un nouveau mot de passe (valable 1 heure)."},
        links={"lien": "Choisir un nouveau mot de passe"},
    ),
    EmailKind.AGENT_ACTIVATION: DefaultText(
        "Activation de votre compte",
        _paragraphs(
            "Bonjour {prénom},",
            "Un compte agent a été créé pour vous (numéro d'employé : {numéro d'employé}).\n"
            "Pour choisir votre mot de passe, ouvrez ce lien (valable 7 jours) :",
            "{lien}",
            "Si le lien a expiré, demandez à l'administrateur de vous en renvoyer un.",
        ),
        {**FIRST_NAME, **EMPLOYEE_NUMBER, "lien": "Lien pour choisir son mot de passe (valable 7 jours)."},
        links={"lien": "Choisir mon mot de passe"},
    ),
    EmailKind.REVIEW_PUBLISHED: DefaultText(
        "Merci, votre avis est en ligne",
        _paragraphs(
            "Bonjour {prénom},",
            "Merci, votre avis « {titre} » sur {destination} est en ligne.",
            "{lien vers la destination}",
        ),
        {
            **FIRST_NAME,
            **REVIEW,
            "lien vers la destination": "Phrase « Vous pouvez le lire sur la page de la destination » suivie du "
            "lien ; absente si la destination n'est pas visible sur le site.",
        },
        links={"lien vers la destination": "Voir la page de la destination"},
    ),
    EmailKind.REVIEW_REFUSED: DefaultText(
        "Votre avis n'est pas publié",
        _paragraphs(
            "Bonjour {prénom},",
            "Votre avis « {titre} » sur {destination} n'est pas publié sur notre site.",
            "Motif : {motif}",
            "{correction}",
        ),
        {
            **FIRST_NAME,
            **REVIEW,
            "motif": "Motif du refus, avec la précision de l'agence s'il y en a une.",
            "correction": "Date limite pour corriger l'avis et lien vers « Mes avis » ; ou phrase indiquant "
            "que le délai de 30 jours est dépassé ; absente si l'avis ne peut pas être corrigé "
            "(voyage annulé).",
        },
        links={"correction": "Corriger mon avis"},
    ),
    EmailKind.REVIEW_RESPONSE: DefaultText(
        "Réponse de l'agence à votre avis",
        _paragraphs(
            "Bonjour {prénom},",
            "{annonce} à votre avis « {titre} » sur {destination}.",
            "Réponse de {auteur} :",
            "{réponse}",
            "Vous retrouvez votre avis et cette réponse sur la page « Mes avis » :",
            "{lien}",
        ),
        {
            **FIRST_NAME,
            "annonce": "« L'agence a répondu », ou « L'agence a modifié sa réponse » si elle l'a modifiée.",
            **REVIEW,
            "auteur": "Prénom de l'agent qui a répondu.",
            "réponse": "Texte de la réponse de l'agence.",
            "lien": "Lien vers la page « Mes avis ».",
        },
        links={"lien": "Voir mes avis"},
    ),
    EmailKind.ORDER_PLACED: DefaultText(
        "Nous avons bien reçu votre demande de voyage",
        _paragraphs(
            "Bonjour {prénom},",
            "Merci pour votre demande de voyage : nous l'avons bien reçue. Un conseiller vous rappellera sous "
            "48 h pour en parler avec vous.",
            "Récapitulatif de votre demande :\n{récapitulatif}",
        ),
        {
            **FIRST_NAME,
            "récapitulatif": "Récapitulatif de la demande, une ligne par information : numéro, destination, "
            "dates, voyageurs, activités, promotion et prix estimé.",
        },
    ),
    EmailKind.ORDER_CONFIRMED: DefaultText(
        "Votre demande de voyage est confirmée",
        _paragraphs(
            "Bonjour {prénom},",
            "Bonne nouvelle : votre demande de voyage est confirmée. Votre conseiller est {conseiller}.",
            "Récapitulatif de votre demande :\n{récapitulatif}",
        ),
        {
            **FIRST_NAME,
            "conseiller": "Prénom et nom de l'agent qui a confirmé la demande.",
            "récapitulatif": "Récapitulatif de la demande, une ligne par information : numéro, destination, "
            "dates, voyageurs, activités, promotion et prix confirmé.",
        },
    ),
    EmailKind.ORDER_CANCELLED_BY_CLIENT: DefaultText(
        "Annulation de votre demande de voyage",
        _paragraphs(
            "Bonjour {prénom},",
            "Nous avons bien enregistré l'annulation de votre demande de voyage n° {numéro} : {destination}, "
            "{dates}.",
            "Nous espérons avoir le plaisir de vous accompagner pour un prochain voyage.",
        ),
        {**FIRST_NAME, **ORDER_NUMBER, **DESTINATION, **DATES},
    ),
    EmailKind.ORDER_CANCELLED_BY_AGENCY: DefaultText(
        "Annulation de votre demande de voyage",
        _paragraphs(
            "Bonjour {prénom},",
            "Nous sommes au regret de vous informer que l'agence a annulé votre demande de voyage n° {numéro} : "
            "{destination}, {dates}.",
            "{explication}",
            "Nous vous prions de nous excuser pour ce désagrément. Pour toute question, n'hésitez pas à nous "
            "contacter.",
        ),
        {
            **FIRST_NAME,
            **ORDER_NUMBER,
            **DESTINATION,
            **DATES,
            "explication": "Ligne « Explication de l'agence : … » ; absente si l'agent n'a rien écrit pour le "
            "client.",
        },
    ),
    EmailKind.NEW_ORDER_ALERT: DefaultText(
        "Nouvelle demande de voyage",
        _paragraphs(
            "Bonjour,",
            "Une nouvelle demande de voyage vient d'être envoyée.",
            "- N° de demande : {numéro}\n- Destination : {destination}\n- Dates : {dates}\n- Client : {client}",
            "Fiche de la demande dans l'espace personnel :\n{lien}",
        ),
        {
            **ORDER_NUMBER,
            **DESTINATION,
            "dates": "Dates du voyage, par exemple « Du 3 mai 2026 au 13 mai 2026 ».",
            "client": "Prénom et nom du client.",
            "lien": "Lien vers la fiche de la demande dans l'espace du personnel.",
        },
        links={"lien": "Ouvrir la fiche de la demande"},
    ),
    EmailKind.DEPARTURE_REMINDER: DefaultText(
        "Votre départ approche",
        _paragraphs(
            "Bonjour {prénom},",
            "Votre voyage approche : départ pour {destination} le {date de départ}, retour le {date de retour} "
            "(demande n° {numéro}).",
            "Quelques rappels pour bien préparer votre départ :",
            "- {pièce d'identité}\n- Visa pour les Belges : {visa}\n{décalage horaire}\n- Monnaie : {monnaie}",
            "Le détail de votre demande :\n{lien}",
            "Nous vous souhaitons un excellent voyage.",
        ),
        {
            **FIRST_NAME,
            **DESTINATION,
            "date de départ": "Date de départ, par exemple « 3 mai 2026 ».",
            "date de retour": "Date de retour, par exemple « 13 mai 2026 ».",
            **ORDER_NUMBER,
            "pièce d'identité": "Phrase sur la pièce d'identité à emporter (passeport ou carte d'identité).",
            "visa": "Règle de visa du pays pour les Belges.",
            "décalage horaire": "Ligne « - Décalage horaire le jour du départ : … » ; absente si le fuseau "
            "horaire du pays n'est pas renseigné.",
            "monnaie": "Monnaie du pays.",
            "lien": "Lien vers le détail de la demande.",
        },
        links={"lien": "Voir ma demande de voyage"},
    ),
    EmailKind.REVIEW_INVITATION: DefaultText(
        "Comment s'est passé votre voyage ?",
        _paragraphs(
            "Bonjour {prénom},",
            "Nous espérons que votre voyage à {destination}, {dates}, s'est bien passé.",
            "Votre avis aide les autres voyageurs à choisir leur destination. Pour le donner, ouvrez ce lien "
            "(connexion à votre compte demandée) :",
            "{lien}",
            "Votre avis sera publié après validation par l'agence. Merci d'avance pour votre retour.",
        ),
        {**FIRST_NAME, **DESTINATION, **DATES, "lien": "Lien vers la page pour donner son avis."},
        links={"lien": "Donner mon avis"},
    ),
    EmailKind.PASSWORD_CHANGED: DefaultText(
        "Votre mot de passe a été modifié",
        _paragraphs(
            "Bonjour {prénom},",
            "Le mot de passe de votre compte vient d'être modifié.",
            "Si c'est bien vous, vous n'avez rien à faire.",
            "Si ce n'est pas vous, contactez-nous sans attendre en répondant à cet e-mail. Vous pouvez aussi "
            "choisir dès maintenant un nouveau mot de passe avec « Mot de passe oublié », sur la page de "
            "connexion.",
        ),
        FIRST_NAME,
    ),
    EmailKind.ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        _paragraphs(
            "Bonjour {prénom},",
            "Comme vous l'avez demandé, votre compte a été supprimé et vos données personnelles ont été effacées.",
            LAST_MESSAGE,
            "Merci de nous avoir fait confiance.",
        ),
        FIRST_NAME,
    ),
    EmailKind.UNCONFIRMED_ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        _paragraphs(
            "Bonjour {prénom},",
            "Un compte a été créé sur notre site avec cette adresse e-mail il y a plus de 30 jours, mais "
            "l'adresse n'a jamais été confirmée. Comme annoncé lors de l'inscription, ce compte a été supprimé "
            "et ses données ont été effacées.",
            "Si vous souhaitez voyager avec nous, vous pouvez créer un nouveau compte à tout moment.",
            LAST_MESSAGE,
        ),
        FIRST_NAME,
    ),
    EmailKind.STAFF_ACCOUNT_DELETED: DefaultText(
        "Votre compte a été supprimé",
        _paragraphs(
            "Bonjour {prénom},",
            "Votre compte du personnel (numéro d'employé : {numéro d'employé}) a été supprimé par "
            "l'administrateur. Vous ne pouvez plus vous connecter au site.",
            LAST_MESSAGE,
        ),
        {**FIRST_NAME, **EMPLOYEE_NUMBER},
    ),
    EmailKind.STAFF_PASSWORD_LINK: DefaultText(
        "Choisissez un nouveau mot de passe",
        _paragraphs(
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
    EmailKind.PROMOTION: DefaultText(
        "Une offre pour votre prochain voyage",
        _paragraphs(
            "Bonjour {prénom},",
            "{message}",
            "{offre}",
            "Découvrez nos voyages :\n{lien}",
            "Au plaisir de préparer votre prochain voyage avec vous.",
            "{désinscription}",
        ),
        {
            **FIRST_NAME,
            "message": "Message écrit par l'administrateur au moment de l'envoi de la promotion.",
            "offre": "Description de l'offre : nom et remise, destinations concernées, dates de validité et, "
            "s'il y en a un, code promo.",
            "lien": "Lien vers les offres du moment ou vers la liste des pays.",
            "désinscription": "Phrase obligatoire qui explique l'envoi, suivie du lien de désinscription.",
        },
        links={"lien": "Découvrir nos voyages", "désinscription": "Me désinscrire"},
    ),
}


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
