"""Compression d’images uploadées : moins de Mo, qualité visuelle conservée."""
from __future__ import annotations

import io
import logging
import os
from typing import BinaryIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile

logger = logging.getLogger(__name__)

# Cibles adaptées à l’affichage Accueil / listes (pas d’impression grand format).
DEFAULT_MAX_SIDE = 1600
AVATAR_MAX_SIDE = 512
MACHINE_MAX_SIDE = 1280
JPEG_QUALITY = 82
WEBP_QUALITY = 80


def _open_image(data: bytes):
    from PIL import Image, ImageOps

    image = Image.open(io.BytesIO(data))
    image = ImageOps.exif_transpose(image)
    return image


def _has_alpha(image) -> bool:
    if image.mode in ('RGBA', 'LA'):
        return True
    if image.mode == 'P' and 'transparency' in image.info:
        return True
    return False


def _to_rgb(image):
    from PIL import Image

    if image.mode == 'RGB':
        return image
    if image.mode == 'L':
        return image.convert('RGB')
    if _has_alpha(image):
        background = image.convert('RGBA')
        canvas = Image.new('RGB', background.size, (255, 255, 255))
        canvas.paste(background, mask=background.split()[-1])
        return canvas
    return image.convert('RGB')


def optimize_image_bytes(
    data: bytes,
    *,
    filename: str = 'photo.jpg',
    max_side: int = DEFAULT_MAX_SIDE,
    quality: int = JPEG_QUALITY,
) -> tuple[bytes, str]:
    """
    Redimensionne + recompresse. Retourne (bytes, nom_fichier).
    JPEG progressif pour photos ; WebP si transparence PNG utile.
    """
    if not data:
        return data, filename

    try:
        from PIL import Image
    except Exception:
        logger.exception('Pillow indisponible — image non optimisée')
        return data, filename

    try:
        image = _open_image(data)
    except Exception:
        logger.exception('Impossible d’ouvrir l’image — fichier original conservé')
        return data, filename

    # GIF animé : on garde le fichier d’origine (évite de casser l’animation).
    if getattr(image, 'is_animated', False) and getattr(image, 'n_frames', 1) > 1:
        return data, filename

    width, height = image.size
    longest = max(width, height)
    if longest > max_side:
        ratio = max_side / float(longest)
        new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    base = os.path.splitext(os.path.basename(filename or 'photo.jpg'))[0] or 'photo'
    out = io.BytesIO()

    try:
        if _has_alpha(image):
            rgba = image.convert('RGBA')
            out_name = f'{base}.webp'
            rgba.save(out, format='WEBP', quality=WEBP_QUALITY, method=4)
        else:
            rgb = _to_rgb(image)
            out_name = f'{base}.jpg'
            rgb.save(
                out,
                format='JPEG',
                quality=quality,
                optimize=True,
                progressive=True,
            )
    except Exception:
        logger.exception('Échec compression — fichier original conservé')
        return data, filename

    optimized = out.getvalue()
    # Si pas de gain de poids (et pas de resize), garder l’original.
    if len(optimized) >= len(data) and longest <= max_side:
        return data, filename
    return optimized, out_name


def optimize_upload(
    upload: UploadedFile | BinaryIO,
    *,
    max_side: int = DEFAULT_MAX_SIDE,
    quality: int = JPEG_QUALITY,
    filename: str | None = None,
) -> ContentFile:
    """Lit un upload, le compresse, renvoie un ContentFile prêt à .save()."""
    name = filename or getattr(upload, 'name', None) or 'photo.jpg'
    try:
        if hasattr(upload, 'seek'):
            upload.seek(0)
        data = upload.read()
    except Exception:
        raise

    optimized, out_name = optimize_image_bytes(
        data,
        filename=name,
        max_side=max_side,
        quality=quality,
    )
    content = ContentFile(optimized)
    content.name = out_name
    return content


def optimize_to_uploaded_file(
    upload: UploadedFile,
    *,
    max_side: int = DEFAULT_MAX_SIDE,
    quality: int = JPEG_QUALITY,
) -> InMemoryUploadedFile:
    """Variante InMemoryUploadedFile (champs ImageField = upload direct)."""
    content = optimize_upload(upload, max_side=max_side, quality=quality)
    content.seek(0)
    data = content.read()
    name = content.name
    content_type = 'image/webp' if name.lower().endswith('.webp') else 'image/jpeg'
    return InMemoryUploadedFile(
        file=io.BytesIO(data),
        field_name=getattr(upload, 'field_name', None),
        name=name,
        content_type=content_type,
        size=len(data),
        charset=None,
    )
