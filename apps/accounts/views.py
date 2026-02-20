"""
Views for user authentication, registration, profile management,
password change, password reset, and profile image upload.

All endpoints follow REST conventions.  Token generation/refresh is
handled by djangorestframework-simplejwt; custom views add registration,
profile CRUD, and the password-reset email flow.

External integrations (SendGrid, Cloudinary) are delegated to dedicated
utility modules so views stay thin and integrations are independently
testable.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from .cloudinary_utils import ImageValidationError, upload_profile_image
from .emails import send_password_reset_email, send_welcome_email
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/

    Creates a new user account and returns JWT tokens so the user is
    logged-in immediately after registration.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Fire-and-forget welcome email (non-blocking)
        send_welcome_email(user)

        # Generate JWT tokens for immediate login
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class LoginView(APIView):
    """
    POST /api/v1/auth/login/

    Authenticates credentials and returns JWT access + refresh tokens
    together with the user profile.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Logout (blacklist refresh token)
# ---------------------------------------------------------------------------
class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklists the supplied refresh token so it can no longer be used.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Successfully logged out."},
                status=status.HTTP_200_OK,
            )
        except Exception:
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ---------------------------------------------------------------------------
# Profile — GET / PATCH
# ---------------------------------------------------------------------------
class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/v1/auth/profile/   → current user's profile
    PATCH /api/v1/auth/profile/  → update profile fields
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Profile Image Upload (Cloudinary)
# ---------------------------------------------------------------------------
class ProfileImageUploadView(APIView):
    """
    POST /api/v1/auth/profile/upload-image/

    Accepts a multipart image file, uploads it to Cloudinary,
    and stores the resulting URL on the user's profile.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        image = request.FILES.get("image")
        if not image:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            url = upload_profile_image(image, user_id=str(request.user.pk))
        except ImageValidationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError:
            return Response(
                {"detail": "Image upload failed. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Persist the Cloudinary URL on the user profile
        request.user.profile_image = url
        request.user.save(update_fields=["profile_image"])

        return Response(
            {
                "profile_image": url,
                "detail": "Profile image uploaded successfully.",
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Change Password
# ---------------------------------------------------------------------------
class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/

    Requires the current password; sets a new one.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Password Reset — Request (send email)
# ---------------------------------------------------------------------------
class PasswordResetRequestView(APIView):
    """
    POST /api/v1/auth/password-reset/

    Generates a one-time token, builds a reset link pointing to the
    frontend, and sends it via SendGrid.  Always returns 200 to prevent
    email enumeration.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Always return success to prevent email enumeration
        success_msg = {
            "detail": "If an account with that email exists, a reset link has been sent."
        }

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            return Response(success_msg, status=status.HTTP_200_OK)

        # Build reset link
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_url = (
            f"{settings.FRONTEND_BASE_URL}/password-reset/confirm"
            f"?uid={uid}&token={token}"
        )

        # Delegate email delivery to the emails module
        send_password_reset_email(user, reset_url)

        return Response(success_msg, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Password Reset — Confirm (validate token + set new password)
# ---------------------------------------------------------------------------
class PasswordResetConfirmView(APIView):
    """
    POST /api/v1/auth/password-reset/confirm/

    Validates the uid/token pair from the email link and sets the new
    password.  The token is single-use (Django's token generator
    incorporates the password hash, so it becomes invalid after use).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid = force_str(
                urlsafe_base64_decode(serializer.validated_data["uid"])
            )
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"detail": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = serializer.validated_data["token"]
        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Reset link has expired or already been used."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response(
            {"detail": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
