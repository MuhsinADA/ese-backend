"""
Serializers for Task and Category models.

Includes enterprise-level validation:
  - Status transition enforcement (todo → in_progress → done)
  - Due-date validation (must not be in the past on creation)
  - Category ownership check (cannot assign another user's category)
  - Computed `is_overdue` field exposed on read
"""

from datetime import date

from rest_framework import serializers

from .models import Category, Task


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    """
    CRUD serializer for Category.

    The `user` field is set automatically from the request — never
    accepted from the client — to enforce ownership.
    `task_count` is a read-only annotation showing how many tasks
    belong to this category.
    """

    task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "name", "colour", "task_count", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_colour(self, value):
        """Ensure colour is a valid hex code."""
        import re

        if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
            raise serializers.ValidationError(
                "Colour must be a valid hex code, e.g. #6366f1."
            )
        return value

    def validate_name(self, value):
        """Check uniqueness within the current user's categories."""
        request = self.context.get("request")
        if not request:
            return value

        qs = Category.objects.filter(name__iexact=value, user=request.user)

        # On update, exclude the current instance
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "You already have a category with this name."
            )
        return value


# ---------------------------------------------------------------------------
# Task (list / detail)
# ---------------------------------------------------------------------------
class TaskSerializer(serializers.ModelSerializer):
    """
    Full serializer for Task CRUD.

    Read-only computed fields:
      - `is_overdue`: boolean — True when due_date < today and status ≠ done
      - `category_name`: shortcut string from the related Category

    Validation rules:
      - `due_date` must not be in the past on creation
      - `status` transitions follow todo → in_progress → done
      - `category` must belong to the requesting user (if provided)
    """

    is_overdue = serializers.BooleanField(read_only=True)
    category_name = serializers.CharField(
        source="category.name", read_only=True, default=None
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "category",
            "category_name",
            "is_overdue",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    # ------------------------------------------------------------------
    # Field-level validation
    # ------------------------------------------------------------------
    def validate_due_date(self, value):
        """On creation, due_date must not be in the past."""
        if value and not self.instance:
            if value < date.today():
                raise serializers.ValidationError(
                    "Due date cannot be in the past."
                )
        return value

    def validate_category(self, value):
        """Category must belong to the requesting user."""
        if value is None:
            return value
        request = self.context.get("request")
        if request and value.user != request.user:
            raise serializers.ValidationError(
                "You can only assign your own categories."
            )
        return value

    # ------------------------------------------------------------------
    # Object-level validation
    # ------------------------------------------------------------------
    VALID_TRANSITIONS = {
        "todo": {"todo", "in_progress"},
        "in_progress": {"in_progress", "done", "todo"},
        "done": {"done", "todo"},
    }

    def validate(self, attrs):
        """Enforce status lifecycle transitions on update."""
        if self.instance and "status" in attrs:
            current = self.instance.status
            requested = attrs["status"]
            if requested not in self.VALID_TRANSITIONS.get(current, set()):
                raise serializers.ValidationError(
                    {
                        "status": (
                            f"Invalid transition from '{current}' to '{requested}'. "
                            f"Allowed: {', '.join(sorted(self.VALID_TRANSITIONS[current]))}."
                        )
                    }
                )
        return attrs


# ---------------------------------------------------------------------------
# Task Statistics (read-only aggregate)
# ---------------------------------------------------------------------------
class TaskStatsSerializer(serializers.Serializer):
    """Read-only serializer for the /tasks/stats/ endpoint."""

    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    by_priority = serializers.DictField(child=serializers.IntegerField())
    overdue = serializers.IntegerField()
