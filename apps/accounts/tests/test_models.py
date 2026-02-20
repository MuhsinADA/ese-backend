"""Tests for the custom User model."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    """Model-level tests: fields, defaults, constraints, __str__."""

    def test_create_user(self):
        user = User.objects.create_user(
            username="modeluser",
            email="model@example.com",
            password="Pass1234!",
        )
        assert user.pk is not None
        assert isinstance(user.pk, uuid.UUID)
        assert user.email == "model@example.com"
        assert user.check_password("Pass1234!")

    def test_uuid_primary_key(self):
        user = User.objects.create_user(
            username="uuidcheck", email="uuid@example.com", password="x"
        )
        assert isinstance(user.pk, uuid.UUID)

    def test_email_unique(self):
        User.objects.create_user(username="a", email="dup@example.com", password="x")
        with pytest.raises(IntegrityError):
            User.objects.create_user(username="b", email="dup@example.com", password="x")

    def test_str_representation(self):
        user = User.objects.create_user(
            username="struser", email="str@example.com", password="x"
        )
        assert str(user) == "struser (str@example.com)"

    def test_default_bio_blank(self):
        user = User.objects.create_user(
            username="biouser", email="bio@example.com", password="x"
        )
        assert user.bio == ""

    def test_default_profile_image_blank(self):
        user = User.objects.create_user(
            username="imguser", email="img@example.com", password="x"
        )
        assert user.profile_image == ""

    def test_ordering_by_date_joined_desc(self):
        u1 = User.objects.create_user(username="first", email="f@x.com", password="x")
        u2 = User.objects.create_user(username="second", email="s@x.com", password="x")
        ordered = list(User.objects.filter(pk__in=[u1.pk, u2.pk]))
        assert ordered[0] == u2  # most recent first
