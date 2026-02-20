"""Tests for accounts serializers."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory

from apps.accounts.serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()
factory = APIRequestFactory()


@pytest.mark.django_db
class TestRegisterSerializer:
    """Registration validation logic."""

    VALID_DATA = {
        "username": "newuser",
        "email": "new@example.com",
        "password": "StrongPass1!",
        "password_confirm": "StrongPass1!",
    }

    def test_valid_registration(self):
        s = RegisterSerializer(data=self.VALID_DATA)
        assert s.is_valid(), s.errors
        user = s.save()
        assert user.username == "newuser"
        assert user.check_password("StrongPass1!")

    def test_password_mismatch(self):
        data = {**self.VALID_DATA, "password_confirm": "Different1!"}
        s = RegisterSerializer(data=data)
        assert not s.is_valid()
        assert "password_confirm" in s.errors

    def test_duplicate_email(self):
        User.objects.create_user(
            username="existing", email="new@example.com", password="x"
        )
        s = RegisterSerializer(data=self.VALID_DATA)
        assert not s.is_valid()
        assert "email" in s.errors

    def test_weak_password_rejected(self):
        data = {**self.VALID_DATA, "password": "123", "password_confirm": "123"}
        s = RegisterSerializer(data=data)
        assert not s.is_valid()
        assert "password" in s.errors

    def test_email_normalised_to_lowercase(self):
        data = {**self.VALID_DATA, "email": "  UPPER@Example.COM  "}
        s = RegisterSerializer(data=data)
        assert s.is_valid(), s.errors
        user = s.save()
        assert user.email == "upper@example.com"


@pytest.mark.django_db
class TestLoginSerializer:
    """Credential validation."""

    def _make_user(self):
        return User.objects.create_user(
            username="loginuser", email="l@x.com", password="StrongPass1!"
        )

    def test_valid_login(self):
        self._make_user()
        s = LoginSerializer(data={"username": "loginuser", "password": "StrongPass1!"})
        assert s.is_valid(), s.errors
        assert s.validated_data["user"].username == "loginuser"

    def test_invalid_password(self):
        self._make_user()
        s = LoginSerializer(data={"username": "loginuser", "password": "wrong"})
        assert not s.is_valid()

    def test_nonexistent_user(self):
        s = LoginSerializer(data={"username": "ghost", "password": "x"})
        assert not s.is_valid()

    def test_inactive_user_rejected(self):
        user = self._make_user()
        user.is_active = False
        user.save()
        s = LoginSerializer(data={"username": "loginuser", "password": "StrongPass1!"})
        assert not s.is_valid()


@pytest.mark.django_db
class TestUserProfileSerializer:
    """Profile read/update."""

    def test_read_only_fields(self):
        user = User.objects.create_user(
            username="profuser", email="p@x.com", password="x"
        )
        s = UserProfileSerializer(user)
        data = s.data
        assert data["username"] == "profuser"
        assert data["email"] == "p@x.com"
        assert "password" not in data

    def test_cannot_change_username_via_serializer(self):
        user = User.objects.create_user(
            username="fixed", email="fix@x.com", password="x"
        )
        s = UserProfileSerializer(user, data={"username": "hacked"}, partial=True)
        assert s.is_valid(), s.errors
        s.save()
        user.refresh_from_db()
        assert user.username == "fixed"  # unchanged — read-only


@pytest.mark.django_db
class TestChangePasswordSerializer:
    """Password change validation."""

    def _context(self, user):
        req = factory.post("/fake/")
        req.user = user
        return {"request": req}

    def test_valid_change(self):
        user = User.objects.create_user(
            username="chguser", email="c@x.com", password="OldPass1!"
        )
        s = ChangePasswordSerializer(
            data={
                "old_password": "OldPass1!",
                "new_password": "NewPass1!",
                "new_password_confirm": "NewPass1!",
            },
            context=self._context(user),
        )
        assert s.is_valid(), s.errors

    def test_wrong_old_password(self):
        user = User.objects.create_user(
            username="chguser2", email="c2@x.com", password="OldPass1!"
        )
        s = ChangePasswordSerializer(
            data={
                "old_password": "wrong",
                "new_password": "NewPass1!",
                "new_password_confirm": "NewPass1!",
            },
            context=self._context(user),
        )
        assert not s.is_valid()
        assert "old_password" in s.errors

    def test_new_passwords_must_match(self):
        user = User.objects.create_user(
            username="chguser3", email="c3@x.com", password="OldPass1!"
        )
        s = ChangePasswordSerializer(
            data={
                "old_password": "OldPass1!",
                "new_password": "NewPass1!",
                "new_password_confirm": "Mismatch1!",
            },
            context=self._context(user),
        )
        assert not s.is_valid()
        assert "new_password_confirm" in s.errors


@pytest.mark.django_db
class TestPasswordResetConfirmSerializer:
    """Password reset token validation."""

    def test_passwords_must_match(self):
        s = PasswordResetConfirmSerializer(
            data={
                "uid": "abc",
                "token": "xyz",
                "new_password": "ResetPass1!",
                "new_password_confirm": "Different1!",
            }
        )
        assert not s.is_valid()
        assert "new_password_confirm" in s.errors

    def test_valid_data(self):
        s = PasswordResetConfirmSerializer(
            data={
                "uid": "abc",
                "token": "xyz",
                "new_password": "ResetPass1!",
                "new_password_confirm": "ResetPass1!",
            }
        )
        assert s.is_valid(), s.errors
