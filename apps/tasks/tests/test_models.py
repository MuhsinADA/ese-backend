"""Tests for Task and Category models."""

import uuid
from datetime import date, timedelta

import pytest
from django.db import IntegrityError

from apps.tasks.models import Category, Task
from conftest import UserFactory, CategoryFactory, TaskFactory


@pytest.mark.django_db
class TestCategoryModel:
    """Category model: fields, defaults, constraints, __str__."""

    def test_create_category(self, user):
        cat = Category.objects.create(name="Work", user=user)
        assert cat.pk is not None
        assert isinstance(cat.pk, uuid.UUID)

    def test_default_colour(self, user):
        cat = Category.objects.create(name="Default", user=user)
        assert cat.colour == "#6366f1"

    def test_str(self, user):
        cat = Category.objects.create(name="Health", user=user)
        assert str(cat) == "Health"

    def test_unique_name_per_user(self, user):
        Category.objects.create(name="Dup", user=user)
        with pytest.raises(IntegrityError):
            Category.objects.create(name="Dup", user=user)

    def test_same_name_different_users(self, user, other_user):
        Category.objects.create(name="Same", user=user)
        cat = Category.objects.create(name="Same", user=other_user)
        assert cat.pk is not None  # no error — different users

    def test_ordering_by_name(self, user):
        Category.objects.create(name="Zebra", user=user)
        Category.objects.create(name="Apple", user=user)
        names = list(Category.objects.filter(user=user).values_list("name", flat=True))
        assert names == sorted(names)


@pytest.mark.django_db
class TestTaskModel:
    """Task model: fields, defaults, is_overdue, constraints, __str__."""

    def test_create_task(self, user):
        t = Task.objects.create(title="Do stuff", user=user)
        assert t.pk is not None
        assert isinstance(t.pk, uuid.UUID)

    def test_default_status_todo(self, user):
        t = Task.objects.create(title="New", user=user)
        assert t.status == Task.Status.TODO

    def test_default_priority_medium(self, user):
        t = Task.objects.create(title="New", user=user)
        assert t.priority == Task.Priority.MEDIUM

    def test_str(self, user):
        t = Task.objects.create(title="My Task", user=user)
        assert str(t) == "My Task"

    def test_is_overdue_true(self, user):
        t = Task.objects.create(
            title="Late",
            user=user,
            due_date=date.today() - timedelta(days=1),
            status=Task.Status.TODO,
        )
        assert t.is_overdue is True

    def test_is_overdue_false_when_done(self, user):
        t = Task.objects.create(
            title="Done late",
            user=user,
            due_date=date.today() - timedelta(days=1),
            status=Task.Status.DONE,
        )
        assert t.is_overdue is False

    def test_is_overdue_false_when_no_due_date(self, user):
        t = Task.objects.create(title="No due", user=user)
        assert t.is_overdue is False

    def test_is_overdue_false_when_future(self, user):
        t = Task.objects.create(
            title="Future",
            user=user,
            due_date=date.today() + timedelta(days=30),
        )
        assert t.is_overdue is False

    def test_category_set_null_on_delete(self, user):
        cat = CategoryFactory(user=user)
        t = Task.objects.create(title="Categorised", user=user, category=cat)
        cat.delete()
        t.refresh_from_db()
        assert t.category is None

    def test_ordering_by_created_at_desc(self, user):
        t1 = Task.objects.create(title="First", user=user)
        t2 = Task.objects.create(title="Second", user=user)
        ordered = list(Task.objects.filter(user=user))
        assert ordered[0] == t2  # most recent first

    def test_cascade_on_user_delete(self, user):
        Task.objects.create(title="Orphan", user=user)
        uid = user.pk
        user.delete()
        assert Task.objects.filter(user_id=uid).count() == 0
