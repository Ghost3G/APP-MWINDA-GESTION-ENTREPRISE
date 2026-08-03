"""Validation sécurisée des fichiers uploadés (avatars, covers, PJ)."""
from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}
IMAGE_CONTENT_TYPE_ALIASES = {
    'image/jpg': 'image/jpeg',
    'image/pjpeg': 'image/jpeg',
    'image/x-png': 'image/png',
    'application/octet-stream': None,  # on se fie à la signature
}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

ATTACHMENT_CONTENT_TYPES = IMAGE_CONTENT_TYPES | {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
}
ATTACHMENT_EXTENSIONS = IMAGE_EXTENSIONS | {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt',
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_AVATAR_SIZE = 5 * 1024 * 1024
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024

_SAFE_NAME_RE = re.compile(r'[^A-Za-z0-9._\- ()\[\]]+')


def safe_filename(name: str, max_length: int = 180) -> str:
    base = os.path.basename((name or 'fichier').replace('\\', '/'))
    cleaned = _SAFE_NAME_RE.sub('_', base).strip(' ._')
    return (cleaned or 'fichier')[:max_length]


def _read_header(upload, size: int = 32) -> bytes:
    try:
        position = upload.tell()
    except Exception:
        position = None
    try:
        header = upload.read(size) or b''
        return header
    finally:
        try:
            if position is None:
                upload.seek(0)
            else:
                upload.seek(position)
        except Exception:
            pass


def sniff_content_kind(upload) -> str | None:
    """Détecte le type réel via signature binaire (pas seulement Content-Type client)."""
    header = _read_header(upload, 32)
    if not header:
        return None

    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    if header.startswith((b'GIF87a', b'GIF89a')):
        return 'image/gif'
    if len(header) >= 12 and header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'image/webp'
    # HEIC / HEIF (souvent iPhone)
    if len(header) >= 12 and header[4:8] == b'ftyp':
        brand = header[8:12]
        if brand in {b'heic', b'heif', b'mif1', b'msf1', b'heim', b'heis'}:
            return 'image/heic'
    if header.startswith(b'%PDF'):
        return 'application/pdf'
    if header.startswith(b'PK\x03\x04'):
        return 'application/zip'
    try:
        header.decode('utf-8')
        if all(32 <= b <= 126 or b in (9, 10, 13) for b in header):
            return 'text/plain'
    except Exception:
        pass
    return None


def validate_upload(
    upload,
    *,
    allowed_types: set[str],
    allowed_extensions: set[str],
    max_size: int,
    require_magic: bool = True,
) -> str | None:
    """Retourne un message d'erreur, ou None si le fichier est acceptable."""
    if not upload:
        return 'Fichier manquant'

    name = getattr(upload, 'name', '') or ''
    normalized = name.replace('\\', '/')
    if '..' in normalized.split('/') or normalized.startswith('/'):
        return 'Nom de fichier invalide'

    size = getattr(upload, 'size', None)
    if size is None:
        return 'Fichier illisible'
    if size <= 0:
        return 'Fichier vide'
    if size > max_size:
        mb = max_size // (1024 * 1024)
        return f'Fichier trop volumineux (max {mb} Mo)'

    ext = os.path.splitext(name)[1].lower()
    if ext and ext not in allowed_extensions:
        return 'Extension de fichier non autorisée (utilisez JPG ou PNG)'

    declared = (getattr(upload, 'content_type', '') or '').lower().strip()
    if declared in IMAGE_CONTENT_TYPE_ALIASES:
        alias = IMAGE_CONTENT_TYPE_ALIASES[declared]
        if alias:
            declared = alias

    sniffed = sniff_content_kind(upload) if require_magic else None
    if sniffed == 'image/heic':
        return 'Format iPhone HEIC non supporté. Exportez la photo en JPG ou PNG.'

    # Images : la signature réelle prime sur le Content-Type navigateur
    if (
        declared in IMAGE_CONTENT_TYPES
        or ext in IMAGE_EXTENSIONS
        or not declared
        or declared == 'application/octet-stream'
    ):
        if require_magic:
            if sniffed not in IMAGE_CONTENT_TYPES or sniffed not in allowed_types:
                return 'Le contenu ne correspond pas à une image JPG/PNG/WEBP/GIF valide'
            return None
        return None

    if declared and declared not in allowed_types:
        if sniffed in IMAGE_CONTENT_TYPES and sniffed in allowed_types:
            return None
        return f'Type de fichier non supporté ({declared or "inconnu"})'

    if not require_magic:
        return None

    if declared == 'application/pdf' or ext == '.pdf':
        if sniffed != 'application/pdf':
            return 'Le contenu ne correspond pas à un PDF valide'
        return None

    if declared in {
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    } or ext in {'.docx', '.xlsx'}:
        if sniffed != 'application/zip':
            return 'Le contenu Office est invalide'
        return None

    if declared == 'text/plain' or ext == '.txt':
        if sniffed in IMAGE_CONTENT_TYPES or sniffed == 'application/pdf':
            return 'Le contenu ne correspond pas à un fichier texte'
        return None

    if declared in {'application/msword', 'application/vnd.ms-excel'} or ext in {'.doc', '.xls'}:
        return None

    if sniffed is None:
        return 'Contenu de fichier non reconnu'

    return None


def validate_image_upload(upload, *, max_size: int = MAX_IMAGE_SIZE) -> str | None:
    return validate_upload(
        upload,
        allowed_types=IMAGE_CONTENT_TYPES,
        allowed_extensions=IMAGE_EXTENSIONS,
        max_size=max_size,
        require_magic=True,
    )


def validate_avatar_upload(upload) -> str | None:
    return validate_image_upload(upload, max_size=MAX_AVATAR_SIZE)


def validate_attachment_upload(upload) -> str | None:
    return validate_upload(
        upload,
        allowed_types=ATTACHMENT_CONTENT_TYPES,
        allowed_extensions=ATTACHMENT_EXTENSIONS,
        max_size=MAX_ATTACHMENT_SIZE,
        require_magic=True,
    )


def store_user_avatar(user, upload) -> str | None:
    """
    Enregistre l'avatar via Cloudinary (si configuré) ou stockage local.
    Retourne un message d'erreur, ou None si OK.
    """
    from django.conf import settings

    try:
        if hasattr(upload, 'seek'):
            upload.seek(0)
    except Exception:
        pass

    if os.environ.get('CLOUDINARY_URL') or getattr(settings, 'CLOUDINARY_STORAGE', None):
        try:
            import cloudinary.uploader
        except Exception as exc:
            logger.exception('Cloudinary import failed')
            return f'Cloudinary indisponible ({exc})'

        try:
            result = cloudinary.uploader.upload(
                upload,
                folder='avatars',
                public_id=f'user_{user.pk}',
                overwrite=True,
                resource_type='image',
                invalidate=True,
                transformation=[{'width': 800, 'height': 800, 'crop': 'limit', 'quality': 'auto'}],
            )
            public_id = result.get('public_id')
            secure_url = result.get('secure_url') or ''
            if not public_id:
                return 'Réponse Cloudinary invalide (pas de public_id).'
            # Stocker le public_id ; l’URL est reconstruite via User.avatar_url
            user.avatar = public_id
            user.save(update_fields=['avatar', 'first_name', 'last_name', 'phone'])
            logger.info('Avatar Cloudinary OK user=%s public_id=%s url=%s', user.pk, public_id, secure_url)
            return None
        except Exception as exc:
            logger.exception('Cloudinary avatar upload failed')
            detail = str(exc).strip() or exc.__class__.__name__
            if len(detail) > 180:
                detail = detail[:177] + '…'
            return f'Échec upload Cloudinary : {detail}'

    try:
        user.avatar = upload
        user.save()
        return None
    except Exception as exc:
        logger.exception('Local avatar upload failed')
        return f'Échec enregistrement photo : {exc}'
