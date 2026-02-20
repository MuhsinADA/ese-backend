"""Task and Category models for the task management domain."""

import uuid
from datetime import date

from django.conf import settings
from django.db import models


class Category(models.Model):
    """
    User-defined category for organising tasks.

    Each category belongs to a single user and has a name + colour.
    Deleting a category sets related tasks' category to NULL.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    colour = models.CharField(
        max_length=7,
        default="#6366f1",
        help_text="Hex colour code, e.g. #6366f1",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]
        # Ensure category names are unique per user
        constraints = [
            models.UniqueConstraint(
                fields=["name", "user"],
                name="unique_category_per_user",
            )
        ]

    def __str__(self):
        return self.name


class Task(models.Model):
    """
    Core domain model — a task belonging to an authenticated user.

    Implements status lifecycle (todo → in_progress → done),
    priority levels, optional due dates, and category association.
    Audit fields (created_at, updated_at) track record history.
    """

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    due_date = models.DateField(null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        """Return True if the task is past its due date and not done."""
        if self.due_date and self.status != self.Status.DONE:
            return self.due_date < date.today()
        return False
