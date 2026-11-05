from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Django's built-in user admin, plus the email and public_id fields."""

    list_display = ["email", "username", "is_staff", "is_active", "date_joined"]
    search_fields = ["email", "username", "first_name", "last_name"]
    readonly_fields = ["public_id"]
    fieldsets = (*DjangoUserAdmin.fieldsets, ("Identifiers", {"fields": ("public_id",)}))
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )
