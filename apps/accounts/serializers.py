"""
Serializers for user registration, login, profile management,
password change, and password reset.

Each serializer includes explicit validation aligned with enterprise
security requirements (password strength, email uniqueness, etc.).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles new-user registration.

    Accepts username, email, password (+ confirmation), and optional
    first/last name.  Runs Django's built-in password validators.
    """

    password = serializers.CharField(
        write_only=True, min_length=8, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    # --- field-level ---
    def validate_email(self, value):
        """Normalise and check uniqueness (case-insensitive)."""
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    # --- object-level ---
    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        return user


# ---------------------------------------------------------------------------
# Login (used alongside SimpleJWT — returns extra user info)
# ---------------------------------------------------------------------------
class LoginSerializer(serializers.Serializer):
    """
    Validates login credentials.  The view itself handles token generation
    via SimpleJWT; this serializer authenticates and returns the user.
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        user = authenticate(
            username=attrs["username"], password=attrs["password"]
        )
        if user is None:
            raise serializers.ValidationError("Invalid username or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


# ---------------------------------------------------------------------------
# User Profile (read / update)
# ---------------------------------------------------------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    """Read / update the authenticated user's profile."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "bio",
            "profile_image",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "email", "date_joined"]


# ---------------------------------------------------------------------------
# Change Password
# ---------------------------------------------------------------------------
class ChangePasswordSerializer(serializers.Serializer):
    """Requires the current password before allowing a change."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(
        write_only=True, min_length=8, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "New passwords do not match."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Password Reset — request (email)
# ---------------------------------------------------------------------------
class PasswordResetRequestSerializer(serializers.Serializer):
    """Accepts an email address and triggers the reset flow."""

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


# ---------------------------------------------------------------------------
# Password Reset — confirm (token + new password)
# ---------------------------------------------------------------------------
class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validates the reset token and sets the new password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, min_length=8, validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )
        return attrs
