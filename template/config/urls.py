"""Root URL map. Each app you add plugs its own urls.py in here."""

from django.conf import settings
from django.contrib import admin
from django.urls import path

urlpatterns = [
    # The admin lives at a path set in the environment, never "admin/" in production.
    path(settings.ADMIN_URL, admin.site.urls),
]
