"""Root URL map. Each app you add plugs its own urls.py in here."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

urlpatterns = [
    # The admin lives at a path set in the environment, never "admin/" in production.
    path(settings.ADMIN_URL, admin.site.urls),
]

# Development serves uploaded files itself. static() adds nothing unless DEBUG is on, so
# production never does: there the reverse proxy serves them (or S3 does).
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
