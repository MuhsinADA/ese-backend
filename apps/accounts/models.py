"""Custom User model with UUID primary key and profile fields."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.

    Uses UUID as primary key (enterprise convention — avoids sequential ID
    enumeration). Adds profile fields for bio and profile image URL.
    Email is required and unique — used alongside username for authentication.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, blank=False)
    bio = models.TextField(max_length=500, blank=True, default="")
    profile_image = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Cloudinary URL for the user's profile image.",
    )

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return f"{self.username} ({self.email})"
