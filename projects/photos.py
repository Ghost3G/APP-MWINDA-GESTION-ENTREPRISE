"""Photos multiples d’un projet. La première sert aussi d’illustration."""
from django.core.files.base import ContentFile

from users.uploads import safe_filename, validate_image_upload

from .models import ProjectPhoto

MAX_PROJECT_PHOTOS = 12


def incoming_photo_files(request, *, include_cover=False):
    files = [upload for upload in request.FILES.getlist('photos') if upload]
    if include_cover:
        cover = request.FILES.get('cover_image')
        if cover and cover not in files:
            files.insert(0, cover)
    return files


def prepare_photo_payloads(files):
    prepared = []
    for upload in files:
        error = validate_image_upload(upload)
        if error:
            return error, []
        try:
            upload.seek(0)
            data = upload.read()
        except Exception:
            return 'Fichier illisible', []
        if not data:
            return 'Fichier vide', []
        name = safe_filename(getattr(upload, 'name', '') or 'photo.jpg')
        prepared.append((name, data))
    if len(prepared) > MAX_PROJECT_PHOTOS:
        return f'Maximum {MAX_PROJECT_PHOTOS} photos par projet.', []
    return None, prepared


def attach_project_photos(project, prepared, user):
    if not prepared:
        return None
    if project.photos.count() + len(prepared) > MAX_PROJECT_PHOTOS:
        return f'Maximum {MAX_PROJECT_PHOTOS} photos par projet.'

    first = None
    actor = user if getattr(user, 'is_authenticated', False) else None
    for name, data in prepared:
        photo = ProjectPhoto(project=project, uploaded_by=actor)
        photo.image.save(name, ContentFile(data), save=True)
        if first is None:
            first = (name, data)

    if first and not project.cover_image:
        project.cover_image.save(first[0], ContentFile(first[1]), save=True)
    return None


def remove_project_photos(project, photo_ids):
    ids = [pk for pk in photo_ids if str(pk).isdigit()]
    if not ids:
        return
    for photo in list(project.photos.filter(id__in=ids)):
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
