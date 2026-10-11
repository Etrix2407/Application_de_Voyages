"""Types et textes d'origine des e-mails des demandes de voyage (v5), déclarés au démarrage.

Ce module est importé par le ready() de l'application (orders/apps.py) : il déclare les types
d'OrderEmail et leur texte d'origine dans le registre des e-mails (accounts/services/email_texts.py).
La valeur de chaque champ variable est donnée par orders/services/emails.py et reminders.py.
"""

from accounts.services.email_texts import FIRST_NAME, DefaultText, paragraphs, register_email_kinds
from orders.models import OrderEmail

ORDER_NUMBER = {"numéro": "Numéro de la demande de voyage."}
# Aussi utilisés par l'invitation à donner un avis (reviews/services/email_texts.py).
DESTINATION = {"destination": "Destination et pays, par exemple « Kyoto (Japon) »."}
DATES = {"dates": "Dates du voyage, par exemple « du 3 mai 2026 au 13 mai 2026 »."}

ORDER_TEXTS = {
    OrderEmail.ORDER_PLACED: DefaultText(
        "Nous avons bien reçu votre demande de voyage",
        paragraphs(
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
    OrderEmail.ORDER_CONFIRMED: DefaultText(
        "Votre demande de voyage est confirmée",
        paragraphs(
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
    OrderEmail.ORDER_CANCELLED_BY_CLIENT: DefaultText(
        "Annulation de votre demande de voyage",
        paragraphs(
            "Bonjour {prénom},",
            "Nous avons bien enregistré l'annulation de votre demande de voyage n° {numéro} : {destination}, "
            "{dates}.",
            "Nous espérons avoir le plaisir de vous accompagner pour un prochain voyage.",
        ),
        {**FIRST_NAME, **ORDER_NUMBER, **DESTINATION, **DATES},
    ),
    OrderEmail.ORDER_CANCELLED_BY_AGENCY: DefaultText(
        "Annulation de votre demande de voyage",
        paragraphs(
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
    OrderEmail.NEW_ORDER_ALERT: DefaultText(
        "Nouvelle demande de voyage",
        paragraphs(
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
    OrderEmail.DEPARTURE_REMINDER: DefaultText(
        "Votre départ approche",
        paragraphs(
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
}

register_email_kinds(OrderEmail, ORDER_TEXTS)
