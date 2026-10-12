"""Types et textes d'origine des e-mails des avis (v5), déclarés au démarrage.

Ce module est importé par le ready() de l'application (reviews/apps.py) : il déclare les types
de ReviewEmail et leur texte d'origine dans le registre des e-mails (accounts/services/email_texts.py).
La valeur de chaque champ variable est donnée par reviews/services/notifications.py et invitations.py.
"""

from accounts.services.email_texts import FIRST_NAME, DefaultText, paragraphs, register_email_kinds
from orders.services.email_texts import DATES, DESTINATION
from reviews.models import ReviewEmail

REVIEW = {
    "titre": "Titre de l'avis.",
    "destination": "Destination et pays de l'avis, par exemple « Kyoto (Japon) ».",
}

REVIEW_TEXTS = {
    ReviewEmail.REVIEW_PUBLISHED: DefaultText(
        "Merci, votre avis est en ligne",
        paragraphs(
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
    ReviewEmail.REVIEW_REFUSED: DefaultText(
        "Votre avis n'est pas publié",
        paragraphs(
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
    ReviewEmail.REVIEW_RESPONSE: DefaultText(
        "Réponse de l'agence à votre avis",
        paragraphs(
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
    ReviewEmail.REVIEW_INVITATION: DefaultText(
        "Comment s'est passé votre voyage ?",
        paragraphs(
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
}

register_email_kinds(ReviewEmail, REVIEW_TEXTS)
