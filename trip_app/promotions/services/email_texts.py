"""Type et texte d'origine de l'e-mail promotionnel (v5), déclarés au démarrage.

Ce module est importé par le ready() de l'application (promotions/apps.py) : il déclare
PromotionEmail et son texte d'origine dans le registre des e-mails (accounts/services/email_texts.py).
La valeur de chaque champ variable est donnée par promotions/services/mailing.py.
"""

from accounts.services.email_texts import FIRST_NAME, DefaultText, paragraphs, register_email_kinds
from promotions.models import PromotionEmail

PROMOTION_TEXTS = {
    PromotionEmail.PROMOTION: DefaultText(
        "Une offre pour votre prochain voyage",
        paragraphs(
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

register_email_kinds(PromotionEmail, PROMOTION_TEXTS)
