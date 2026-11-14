"""Root URL map. Each app you add plugs its own urls.py in here."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from config.csp_report import csp_report
from config.uploads import download

urlpatterns = [
    # The admin lives at a path set in the environment, never "admin/" in production.
    path(settings.ADMIN_URL, admin.site.urls),
    # Where browsers report what the Content Security Policy blocked.
    path("csp-report/", csp_report, name="csp-report"),
    # Private uploads: only for those config/uploads.py allows, in every environment.
    # (Django adds a leading / to MEDIA_URL; URL patterns have none.)
    path(f"{settings.MEDIA_URL.lstrip('/')}<path:name>", download, name="private-upload"),
]

# Public uploads: development serves them itself. static() adds nothing unless DEBUG is
# on, so production never does: there Caddy serves them (deploy/Caddyfile), or S3 does.
urlpatterns += static(settings.PUBLIC_MEDIA_URL, document_root=settings.PUBLIC_MEDIA_ROOT)
