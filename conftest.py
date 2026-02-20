"""
Root conftest — shared pytest fixtures and factory-boy factories.

All fixtures use the ``db`` marker implicitly via ``@pytest.mark.django_db``
on individual tests, or via ``autouse`` where noted.
"""

import pytest
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Factory imports (defined below for co-location; split to factories.py if
# the file grows beyond ~100 lines)
# ---------------------------------------------------------------------------
import factory
from django.contrib.auth import get_user_model
from apps.tasks.models import Category, Task

User = get_user_model()


# ===================================================================
# Factories
# ===================================================================

class UserFactory(factory.django.DjangoModelFactory):
    """Create a User with a hashed password and unique username/email."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"testuser{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGeneration(
        lambda obj, create, extracted, **kw: obj.set_password(extracted or "TestPass123!")
        or obj.save()
    )


class CategoryFactory(factory.django.DjangoModelFactory):
    """Create a Category owned by a given user."""

    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    colour = "#6366f1"
    user = factory.SubFactory(UserFactory)


class TaskFactory(factory.django.DjangoModelFactory):
    """Create a Task owned by a given user."""

    class Meta:
        model = Task

    title = factory.Sequence(lambda n: f"Task {n}")
    description = "A test task"
    status = Task.Status.TODO
    priority = Task.Priority.MEDIUM
    user = factory.SubFactory(UserFactory)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def api_client():
    """Unauthenticated DRF test client."""
    return APIClient()


@pytest.fixture
def user(db):
    """A persisted User instance (password: TestPass123!)."""
    return UserFactory()


@pytest.fixture
def other_user(db):
    """A second user for cross-user isolation tests."""
    return UserFactory()


@pytest.fixture
def auth_client(user):
    """Authenticated DRF client for ``user``."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def other_auth_client(other_user):
    """Authenticated DRF client for ``other_user``."""
    client = APIClient()
    client.force_authenticate(user=other_user)
    return client


@pytest.fixture
def category(user):
    """A Category owned by ``user``."""
    return CategoryFactory(user=user)


@pytest.fixture
def task(user):
    """A Task owned by ``user``."""
    return TaskFactory(user=user)
