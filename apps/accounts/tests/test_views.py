"""
API-level tests for all accounts/auth endpoints.

Uses DRF's APIClient (no real HTTP — runs in-process against Django's
test request/response cycle).
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from unittest.mock import patch

User = get_user_model()

# Reusable registration payload
REG_DATA = {
    "username": "viewuser",
    "email": "view@example.com",
    "password": "ViewPass1!",
    "password_confirm": "ViewPass1!",
}


# ===================================================================
# Registration
# ===================================================================
@pytest.mark.django_db
class TestRegisterView:

    URL = "/api/v1/auth/register/"

    def test_success(self, api_client):
        r = api_client.post(self.URL, REG_DATA, format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert "tokens" in r.data
        assert "access" in r.data["tokens"]
        assert "refresh" in r.data["tokens"]
        assert r.data["user"]["username"] == "viewuser"

    def test_duplicate_username(self, api_client, user):
        data = {**REG_DATA, "username": user.username, "email": "unique@x.com"}
        r = api_client.post(self.URL, data, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_email(self, api_client):
        api_client.post(self.URL, REG_DATA, format="json")
        data = {**REG_DATA, "username": "another"}
        r = api_client.post(self.URL, data, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_fields(self, api_client):
        r = api_client.post(self.URL, {}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("apps.accounts.views.send_welcome_email")
    def test_welcome_email_called(self, mock_email, api_client):
        api_client.post(self.URL, REG_DATA, format="json")
        mock_email.assert_called_once()


# ===================================================================
# Login
# ===================================================================
@pytest.mark.django_db
class TestLoginView:

    URL = "/api/v1/auth/login/"

    def test_success(self, api_client, user):
        r = api_client.post(
            self.URL,
            {"username": user.username, "password": "TestPass123!"},
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        assert "tokens" in r.data
        assert r.data["user"]["username"] == user.username

    def test_wrong_password(self, api_client, user):
        r = api_client.post(
            self.URL,
            {"username": user.username, "password": "wrong"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_user(self, api_client):
        r = api_client.post(
            self.URL,
            {"username": "ghost", "password": "x"},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ===================================================================
# Logout
# ===================================================================
@pytest.mark.django_db
class TestLogoutView:

    URL = "/api/v1/auth/logout/"

    def test_success(self, api_client, user):
        # First obtain a real token pair
        login_r = api_client.post(
            "/api/v1/auth/login/",
            {"username": user.username, "password": "TestPass123!"},
            format="json",
        )
        tokens = login_r.data["tokens"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        r = api_client.post(self.URL, {"refresh": tokens["refresh"]}, format="json")
        assert r.status_code == status.HTTP_200_OK

    def test_missing_refresh_token(self, auth_client):
        r = auth_client.post(self.URL, {}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated(self, api_client):
        r = api_client.post(self.URL, {"refresh": "x"}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


# ===================================================================
# Profile
# ===================================================================
@pytest.mark.django_db
class TestProfileView:

    URL = "/api/v1/auth/profile/"

    def test_get_profile(self, auth_client, user):
        r = auth_client.get(self.URL)
        assert r.status_code == status.HTTP_200_OK
        assert r.data["username"] == user.username
        assert r.data["email"] == user.email

    def test_patch_bio(self, auth_client, user):
        r = auth_client.patch(self.URL, {"bio": "Updated bio"}, format="json")
        assert r.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.bio == "Updated bio"

    def test_read_only_fields_immutable(self, auth_client, user):
        r = auth_client.patch(
            self.URL, {"username": "hacked", "email": "hacked@x.com"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.username != "hacked"
        assert user.email != "hacked@x.com"

    def test_unauthenticated(self, api_client):
        r = api_client.get(self.URL)
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


# ===================================================================
# Profile Image Upload
# ===================================================================
@pytest.mark.django_db
class TestProfileImageUploadView:

    URL = "/api/v1/auth/profile/upload-image/"

    def test_no_file(self, auth_client):
        r = auth_client.post(self.URL)
        assert r.status_code == status.HTTP_400_BAD_REQUEST
        assert "No image" in r.data["detail"]

    def test_invalid_content_type(self, auth_client):
        from io import BytesIO
        f = BytesIO(b"not an image")
        f.name = "test.txt"
        r = auth_client.post(self.URL, {"image": f}, format="multipart")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_oversized_file(self, auth_client):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile

        big = SimpleUploadedFile(
            "big.png",
            b"\x00" * (5 * 1024 * 1024 + 1),
            content_type="image/png",
        )
        r = auth_client.post(self.URL, {"image": big}, format="multipart")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    @patch("cloudinary.uploader.upload")
    @patch("apps.accounts.cloudinary_utils._configure_cloudinary")
    def test_successful_upload(self, mock_config, mock_upload, auth_client, user):
        from django.core.files.uploadedfile import SimpleUploadedFile

        mock_upload.return_value = {"secure_url": "https://cdn.example.com/img.jpg"}
        img = SimpleUploadedFile("face.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
        r = auth_client.post(self.URL, {"image": img}, format="multipart")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["profile_image"] == "https://cdn.example.com/img.jpg"
        user.refresh_from_db()
        assert user.profile_image == "https://cdn.example.com/img.jpg"


# ===================================================================
# Change Password
# ===================================================================
@pytest.mark.django_db
class TestChangePasswordView:

    URL = "/api/v1/auth/change-password/"

    def test_success(self, auth_client, user):
        r = auth_client.post(
            self.URL,
            {
                "old_password": "TestPass123!",
                "new_password": "NewPass456!",
                "new_password_confirm": "NewPass456!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("NewPass456!")

    def test_wrong_old_password(self, auth_client):
        r = auth_client.post(
            self.URL,
            {
                "old_password": "wrong",
                "new_password": "NewPass456!",
                "new_password_confirm": "NewPass456!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated(self, api_client):
        r = api_client.post(self.URL, {}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


# ===================================================================
# Password Reset Request
# ===================================================================
@pytest.mark.django_db
class TestPasswordResetRequestView:

    URL = "/api/v1/auth/password-reset/"

    @patch("apps.accounts.views.send_password_reset_email")
    def test_existing_email(self, mock_email, api_client, user):
        r = api_client.post(self.URL, {"email": user.email}, format="json")
        assert r.status_code == status.HTTP_200_OK
        assert "If an account" in r.data["detail"]
        mock_email.assert_called_once()

    @patch("apps.accounts.views.send_password_reset_email")
    def test_unknown_email_still_200(self, mock_email, api_client):
        r = api_client.post(
            self.URL, {"email": "unknown@x.com"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK
        mock_email.assert_not_called()

    def test_missing_email(self, api_client):
        r = api_client.post(self.URL, {}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ===================================================================
# Password Reset Confirm
# ===================================================================
@pytest.mark.django_db
class TestPasswordResetConfirmView:

    URL = "/api/v1/auth/password-reset/confirm/"

    def test_valid_token(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        r = api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "ResetPass1!",
                "new_password_confirm": "ResetPass1!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password("ResetPass1!")

    def test_invalid_token(self, api_client, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        r = api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": "bad-token",
                "new_password": "ResetPass1!",
                "new_password_confirm": "ResetPass1!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_uid(self, api_client):
        r = api_client.post(
            self.URL,
            {
                "uid": "invalid",
                "token": "anything",
                "new_password": "ResetPass1!",
                "new_password_confirm": "ResetPass1!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_token_single_use(self, api_client, user):
        """Token is invalidated after use (Django embeds password hash)."""
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        # First use — succeeds
        api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "ResetPass1!",
                "new_password_confirm": "ResetPass1!",
            },
            format="json",
        )
        # Second use — fails (password hash changed → token invalid)
        r = api_client.post(
            self.URL,
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherPass1!",
                "new_password_confirm": "AnotherPass1!",
            },
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


# ===================================================================
# Token Refresh
# ===================================================================
@pytest.mark.django_db
class TestTokenRefresh:

    URL = "/api/v1/auth/token/refresh/"

    def test_refresh(self, api_client, user):
        login_r = api_client.post(
            "/api/v1/auth/login/",
            {"username": user.username, "password": "TestPass123!"},
            format="json",
        )
        refresh = login_r.data["tokens"]["refresh"]
        r = api_client.post(self.URL, {"refresh": refresh}, format="json")
        assert r.status_code == status.HTTP_200_OK
        assert "access" in r.data

    def test_invalid_refresh_token(self, api_client):
        r = api_client.post(self.URL, {"refresh": "bad"}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
