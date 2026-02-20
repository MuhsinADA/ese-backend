"""
Accounts URL configuration.

All endpoints are mounted under /api/v1/auth/ by the root URL config.
Token refresh is handled by SimpleJWT's built-in view.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    ProfileImageUploadView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
)

urlpatterns = [
    # Authentication
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),

    # Profile management
    path("profile/", ProfileView.as_view(), name="auth-profile"),
    path("profile/upload-image/", ProfileImageUploadView.as_view(), name="auth-profile-upload-image"),

    # Password management
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]
