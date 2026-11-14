"""Private uploads: who may download them, and the view that checks it.

Uploads are private by default: nothing serves the folder they're in. A file's address
(/media/<name>) comes here, and only someone can_download() allows gets it; everyone else
gets a 404, so even whether a file exists stays private. Files anyone may see go in the
"public" storage instead (see the README's Uploaded files section).
"""

from urllib.parse import quote
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage, storages
from django.http import FileResponse, Http404, HttpResponse

# What a private file is sent with, by Django or by Caddy: always a download (an uploaded
# HTML or SVG file can't run scripts on this site), never kept by shared caches.
DOWNLOAD_HEADERS = {
    "Content-Disposition": "attachment",
    "Content-Security-Policy": "default-src 'none'; sandbox",
    "Cache-Control": "private",
}


def can_download(user, name):
    """Whether this user may download the private file `name`. Change this for your
    project, e.g. check that the user owns the object the file belongs to. Until then,
    only active staff can."""
    return user.is_active and user.is_staff


def random_folder(instance, filename):
    """An upload_to for file fields: each file in its own random folder, so a leaked or
    guessed address isn't enough on its own. FileField(upload_to=random_folder)."""
    return f"{uuid4().hex}/{filename}"


def public_storage():
    """The storage for files anyone may see: FileField(storage=public_storage). A
    function, so migrations record its name rather than this machine's folder."""
    return storages["public"]


def download(request, name):
    """A private file, for those can_download() allows; a 404 for everyone else."""
    try:
        allowed = can_download(request.user, name) and default_storage.exists(name)
    except SuspiciousFileOperation:  # a name outside the uploads folder, e.g. ../
        allowed = False
    if not allowed:
        raise Http404
    if settings.MEDIA_SENT_BY_PROXY:
        # Caddy sends the file itself (deploy/Caddyfile), so no Gunicorn worker is tied
        # up streaming it.
        response = HttpResponse()
        response["X-Accel-Redirect"] = "/" + quote(name)  # e.g. spaces and # escaped
    else:
        response = FileResponse(default_storage.open(name))
    for header, value in DOWNLOAD_HEADERS.items():
        response[header] = value
    return response
