"""Nettoyage des photos envoyées : aucune donnée cachée n'est publiée avec l'image."""

import io

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

JPEG_QUALITY = 90


def without_metadata(photo) -> ContentFile:
    """Copie de la photo sans ses métadonnées (EXIF : position GPS, appareil, date de prise de vue).

    L'image est réenregistrée pixel par pixel dans le même format : seules les données
    visibles sont gardées, ce qui écarte aussi tout contenu caché dans le fichier.
    L'orientation EXIF est d'abord appliquée, pour qu'une photo prise de travers reste droite.
    """
    photo.seek(0)
    with Image.open(photo) as original:
        image_format = original.format
        upright = ImageOps.exif_transpose(original)
        # Nouvelle image vierge : ni EXIF, ni commentaires, ni texte intégré.
        clean = Image.new(upright.mode, upright.size)
        clean.paste(upright)
    buffer = io.BytesIO()
    options = {"quality": JPEG_QUALITY} if image_format == "JPEG" else {}
    clean.save(buffer, format=image_format, **options)
    return ContentFile(buffer.getvalue(), name=photo.name)
