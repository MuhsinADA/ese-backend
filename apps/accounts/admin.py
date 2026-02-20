"""Admin configuration for the accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin view for the User model."""

    list_display = ("username", "email", "first_name", "last_name", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)

    # Add profile fields to the admin form
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profile", {"fields": ("bio", "profile_image")}),
    )
