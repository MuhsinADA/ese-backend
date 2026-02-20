"""Tests for Task and Category serializers."""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIRequestFactory

from apps.tasks.models import Category, Task
from apps.tasks.serializers import CategorySerializer, TaskSerializer
from conftest import UserFactory, CategoryFactory, TaskFactory

factory = APIRequestFactory()


def _fake_request(user):
    """Return a minimal DRF request with ``user`` set."""
    req = factory.get("/fake/")
    req.user = user
    return req


# ===================================================================
# Category serializer
# ===================================================================
@pytest.mark.django_db
class TestCategorySerializer:

    def test_valid_create(self, user):
        req = _fake_request(user)
        s = CategorySerializer(
            data={"name": "Work", "colour": "#ef4444"},
            context={"request": req},
        )
        assert s.is_valid(), s.errors

    def test_invalid_colour(self, user):
        req = _fake_request(user)
        s = CategorySerializer(
            data={"name": "Bad", "colour": "red"},
            context={"request": req},
        )
        assert not s.is_valid()
        assert "colour" in s.errors

    def test_duplicate_name_rejected(self, user):
        CategoryFactory(name="Dup", user=user)
        req = _fake_request(user)
        s = CategorySerializer(
            data={"name": "Dup"},
            context={"request": req},
        )
        assert not s.is_valid()
        assert "name" in s.errors

    def test_same_name_different_user_ok(self, user, other_user):
        CategoryFactory(name="Shared", user=user)
        req = _fake_request(other_user)
        s = CategorySerializer(
            data={"name": "Shared"},
            context={"request": req},
        )
        assert s.is_valid(), s.errors

    def test_task_count_present(self, user):
        cat = CategoryFactory(user=user)
        TaskFactory(user=user, category=cat)
        TaskFactory(user=user, category=cat)
        # Simulate annotated queryset
        from django.db.models import Count

        cat_qs = Category.objects.filter(pk=cat.pk).annotate(task_count=Count("tasks"))
        s = CategorySerializer(cat_qs.first())
        assert s.data["task_count"] == 2


# ===================================================================
# Task serializer
# ===================================================================
@pytest.mark.django_db
class TestTaskSerializer:

    def test_valid_create(self, user):
        req = _fake_request(user)
        s = TaskSerializer(
            data={"title": "New task"},
            context={"request": req},
        )
        assert s.is_valid(), s.errors

    def test_due_date_in_past_rejected_on_create(self, user):
        req = _fake_request(user)
        s = TaskSerializer(
            data={"title": "Past", "due_date": str(date.today() - timedelta(days=1))},
            context={"request": req},
        )
        assert not s.is_valid()
        assert "due_date" in s.errors

    def test_due_date_in_past_allowed_on_update(self, user):
        """Editing an existing task shouldn't block a past due_date."""
        task = TaskFactory(
            user=user, due_date=date.today() - timedelta(days=5)
        )
        req = _fake_request(user)
        s = TaskSerializer(
            task,
            data={"title": "Edited"},
            partial=True,
            context={"request": req},
        )
        assert s.is_valid(), s.errors

    def test_category_ownership_enforced(self, user, other_user):
        other_cat = CategoryFactory(user=other_user)
        req = _fake_request(user)
        s = TaskSerializer(
            data={"title": "Steal cat", "category": str(other_cat.pk)},
            context={"request": req},
        )
        assert not s.is_valid()
        assert "category" in s.errors

    def test_own_category_allowed(self, user):
        cat = CategoryFactory(user=user)
        req = _fake_request(user)
        s = TaskSerializer(
            data={"title": "My cat", "category": str(cat.pk)},
            context={"request": req},
        )
        assert s.is_valid(), s.errors

    # --- Status transitions ---

    def _transition(self, user, from_status, to_status):
        task = TaskFactory(user=user, status=from_status)
        req = _fake_request(user)
        s = TaskSerializer(
            task,
            data={"status": to_status},
            partial=True,
            context={"request": req},
        )
        return s

    def test_transition_todo_to_in_progress(self, user):
        s = self._transition(user, "todo", "in_progress")
        assert s.is_valid(), s.errors

    def test_transition_in_progress_to_done(self, user):
        s = self._transition(user, "in_progress", "done")
        assert s.is_valid(), s.errors

    def test_transition_done_to_todo(self, user):
        s = self._transition(user, "done", "todo")
        assert s.is_valid(), s.errors

    def test_transition_todo_to_done_blocked(self, user):
        s = self._transition(user, "todo", "done")
        assert not s.is_valid()
        assert "status" in s.errors

    def test_transition_done_to_in_progress_blocked(self, user):
        s = self._transition(user, "done", "in_progress")
        assert not s.is_valid()
        assert "status" in s.errors

    def test_is_overdue_in_output(self, user):
        task = TaskFactory(
            user=user,
            due_date=date.today() - timedelta(days=1),
            status="todo",
        )
        req = _fake_request(user)
        s = TaskSerializer(task, context={"request": req})
        assert s.data["is_overdue"] is True

    def test_category_name_in_output(self, user):
        cat = CategoryFactory(user=user, name="Work")
        task = TaskFactory(user=user, category=cat)
        req = _fake_request(user)
        s = TaskSerializer(task, context={"request": req})
        assert s.data["category_name"] == "Work"
