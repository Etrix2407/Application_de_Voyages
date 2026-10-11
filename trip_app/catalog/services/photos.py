"""Nettoyage des photos envoyées : aucune donnée cachée n'est publiée avec l'image,
et l'image est ramenée à une taille raisonnable pour l'affichage."""

import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

JPEG_QUALITY = 90
# Côté le plus long d'une photo publiée, en pixels : assez net sur un grand écran.
MAX_PHOTO_SIDE = 1600


def without_metadata(photo) -> ContentFile:
    """Copie de la photo sans ses métadonnées (EXIF : position GPS, appareil, date de prise de vue).

    L'image est réenregistrée pixel par pixel dans le même format : seules les données
    visibles sont gardées, ce qui écarte aussi tout contenu caché dans le fichier.
    L'orientation EXIF est d'abord appliquée, pour qu'une photo prise de travers reste droite,
    puis l'image est réduite (proportions gardées) si un côté dépasse MAX_PHOTO_SIDE.
    """
    photo.seek(0)
    with Image.open(photo) as original:
        image_format = original.format
        # JPEG : décodage directement à taille réduite, sans charger toute l'image en mémoire.
        original.draft(original.mode, (MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
        upright = ImageOps.exif_transpose(original)
        upright.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
        # Image en palette (PNG 8 bits) : passée en vraies couleurs, sinon la copie ci-dessous
        # perdrait la palette et la photo sortirait noire.
        if upright.mode == "P":
            upright = upright.convert("RGBA" if "transparency" in upright.info else "RGB")
        # Nouvelle image vierge : ni EXIF, ni commentaires, ni texte intégré.
        clean = Image.new(upright.mode, upright.size)
        clean.paste(upright)
    buffer = io.BytesIO()
    options = {"quality": JPEG_QUALITY} if image_format == "JPEG" else {}
    clean.save(buffer, format=image_format, **options)
    return ContentFile(buffer.getvalue(), name=photo.name)
