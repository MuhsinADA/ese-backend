"""
API-level tests for Task and Category ViewSets.

Covers CRUD, filtering, search, ordering, stats, pagination,
cross-user isolation, and permission enforcement.
"""

from datetime import date, timedelta

import pytest
from rest_framework import status

from apps.tasks.models import Task
from conftest import CategoryFactory, TaskFactory


# ===================================================================
# Category CRUD
# ===================================================================
@pytest.mark.django_db
class TestCategoryViewSet:

    LIST_URL = "/api/v1/categories/"

    def detail_url(self, pk):
        return f"/api/v1/categories/{pk}/"

    def test_create(self, auth_client, user):
        r = auth_client.post(
            self.LIST_URL,
            {"name": "Work", "colour": "#ef4444"},
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["name"] == "Work"

    def test_list(self, auth_client, user):
        CategoryFactory(user=user, name="A")
        CategoryFactory(user=user, name="B")
        r = auth_client.get(self.LIST_URL)
        assert r.status_code == status.HTTP_200_OK
        assert r.data["count"] == 2

    def test_list_has_task_count(self, auth_client, user):
        cat = CategoryFactory(user=user)
        TaskFactory(user=user, category=cat)
        r = auth_client.get(self.LIST_URL)
        assert r.data["results"][0]["task_count"] == 1

    def test_update(self, auth_client, user):
        cat = CategoryFactory(user=user, name="Old")
        r = auth_client.patch(
            self.detail_url(cat.pk), {"name": "New"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.data["name"] == "New"

    def test_delete(self, auth_client, user):
        cat = CategoryFactory(user=user)
        r = auth_client.delete(self.detail_url(cat.pk))
        assert r.status_code == status.HTTP_204_NO_CONTENT

    def test_duplicate_name_rejected(self, auth_client, user):
        CategoryFactory(user=user, name="Dup")
        r = auth_client.post(self.LIST_URL, {"name": "Dup"}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_cross_user_isolation(self, auth_client, other_user):
        """User A cannot see User B's categories."""
        CategoryFactory(user=other_user)
        r = auth_client.get(self.LIST_URL)
        assert r.data["count"] == 0

    def test_cross_user_detail_404(self, auth_client, other_user):
        cat = CategoryFactory(user=other_user)
        r = auth_client.get(self.detail_url(cat.pk))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated(self, api_client):
        r = api_client.get(self.LIST_URL)
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


# ===================================================================
# Task CRUD
# ===================================================================
@pytest.mark.django_db
class TestTaskViewSet:

    LIST_URL = "/api/v1/tasks/"

    def detail_url(self, pk):
        return f"/api/v1/tasks/{pk}/"

    # --- Create ---
    def test_create_minimal(self, auth_client, user):
        r = auth_client.post(self.LIST_URL, {"title": "Task 1"}, format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["status"] == "todo"
        assert r.data["priority"] == "medium"

    def test_create_full(self, auth_client, user):
        cat = CategoryFactory(user=user)
        r = auth_client.post(
            self.LIST_URL,
            {
                "title": "Full task",
                "description": "Details",
                "priority": "high",
                "due_date": str(date.today() + timedelta(days=7)),
                "category": str(cat.pk),
            },
            format="json",
        )
        assert r.status_code == status.HTTP_201_CREATED
        assert str(r.data["category"]) == str(cat.pk)
        assert r.data["category_name"] == cat.name

    def test_create_invalid_due_date(self, auth_client, user):
        r = auth_client.post(
            self.LIST_URL,
            {"title": "Past", "due_date": str(date.today() - timedelta(days=1))},
            format="json",
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_empty_title(self, auth_client):
        r = auth_client.post(self.LIST_URL, {"title": ""}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    # --- Read ---
    def test_list(self, auth_client, user):
        TaskFactory.create_batch(3, user=user)
        r = auth_client.get(self.LIST_URL)
        assert r.status_code == status.HTTP_200_OK
        assert r.data["count"] == 3

    def test_detail(self, auth_client, task):
        r = auth_client.get(self.detail_url(task.pk))
        assert r.status_code == status.HTTP_200_OK
        assert r.data["title"] == task.title

    def test_pagination(self, auth_client, user):
        TaskFactory.create_batch(15, user=user)
        r = auth_client.get(self.LIST_URL)
        assert r.data["count"] == 15
        assert len(r.data["results"]) == 10  # PAGE_SIZE

    # --- Update ---
    def test_update(self, auth_client, task):
        r = auth_client.patch(
            self.detail_url(task.pk), {"title": "Updated"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.data["title"] == "Updated"

    # --- Status transitions ---
    def test_valid_transition_todo_to_in_progress(self, auth_client, task):
        r = auth_client.patch(
            self.detail_url(task.pk), {"status": "in_progress"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK

    def test_invalid_transition_todo_to_done(self, auth_client, task):
        r = auth_client.patch(
            self.detail_url(task.pk), {"status": "done"}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_valid_lifecycle_todo_inprog_done(self, auth_client, task):
        """Complete lifecycle: todo → in_progress → done."""
        auth_client.patch(
            self.detail_url(task.pk), {"status": "in_progress"}, format="json"
        )
        r = auth_client.patch(
            self.detail_url(task.pk), {"status": "done"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.data["status"] == "done"

    def test_done_to_todo_restart(self, auth_client, user):
        task = TaskFactory(user=user, status="in_progress")
        auth_client.patch(
            self.detail_url(task.pk), {"status": "done"}, format="json"
        )
        r = auth_client.patch(
            self.detail_url(task.pk), {"status": "todo"}, format="json"
        )
        assert r.status_code == status.HTTP_200_OK

    def test_done_to_in_progress_blocked(self, auth_client, user):
        task = TaskFactory(user=user, status="in_progress")
        auth_client.patch(
            self.detail_url(task.pk), {"status": "done"}, format="json"
        )
        r = auth_client.patch(
            self.detail_url(task.pk), {"status": "in_progress"}, format="json"
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    # --- Delete ---
    def test_delete(self, auth_client, task):
        r = auth_client.delete(self.detail_url(task.pk))
        assert r.status_code == status.HTTP_204_NO_CONTENT
        r2 = auth_client.get(self.detail_url(task.pk))
        assert r2.status_code == status.HTTP_404_NOT_FOUND

    # --- Cross-user isolation ---
    def test_cross_user_list_empty(self, auth_client, other_user):
        TaskFactory(user=other_user)
        r = auth_client.get(self.LIST_URL)
        assert r.data["count"] == 0

    def test_cross_user_detail_404(self, auth_client, other_user):
        other_task = TaskFactory(user=other_user)
        r = auth_client.get(self.detail_url(other_task.pk))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_user_update_404(self, auth_client, other_user):
        other_task = TaskFactory(user=other_user)
        r = auth_client.patch(
            self.detail_url(other_task.pk), {"title": "Hacked"}, format="json"
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_cross_user_delete_404(self, auth_client, other_user):
        other_task = TaskFactory(user=other_user)
        r = auth_client.delete(self.detail_url(other_task.pk))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    # --- Unauthenticated ---
    def test_unauthenticated_list(self, api_client):
        r = api_client.get(self.LIST_URL)
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_create(self, api_client):
        r = api_client.post(self.LIST_URL, {"title": "x"}, format="json")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED


# ===================================================================
# Filtering, Search, Ordering
# ===================================================================
@pytest.mark.django_db
class TestTaskFiltering:

    LIST_URL = "/api/v1/tasks/"

    def test_filter_by_status(self, auth_client, user):
        TaskFactory(user=user, status="todo")
        TaskFactory(user=user, status="in_progress")
        TaskFactory(user=user, status="done")
        r = auth_client.get(f"{self.LIST_URL}?status=todo")
        assert r.data["count"] == 1
        assert r.data["results"][0]["status"] == "todo"

    def test_filter_csv_status(self, auth_client, user):
        TaskFactory(user=user, status="todo")
        TaskFactory(user=user, status="in_progress")
        TaskFactory(user=user, status="done")
        r = auth_client.get(f"{self.LIST_URL}?status=todo,in_progress")
        assert r.data["count"] == 2

    def test_filter_by_priority(self, auth_client, user):
        TaskFactory(user=user, priority="low")
        TaskFactory(user=user, priority="urgent")
        r = auth_client.get(f"{self.LIST_URL}?priority=urgent")
        assert r.data["count"] == 1

    def test_filter_by_category(self, auth_client, user):
        cat = CategoryFactory(user=user)
        TaskFactory(user=user, category=cat)
        TaskFactory(user=user)  # no category
        r = auth_client.get(f"{self.LIST_URL}?category={cat.pk}")
        assert r.data["count"] == 1

    def test_filter_overdue(self, auth_client, user):
        TaskFactory(user=user, due_date=date.today() - timedelta(days=1), status="todo")
        TaskFactory(user=user, due_date=date.today() + timedelta(days=30), status="todo")
        r = auth_client.get(f"{self.LIST_URL}?overdue=true")
        assert r.data["count"] == 1

    def test_filter_due_date_range(self, auth_client, user):
        TaskFactory(user=user, due_date=date(2026, 6, 15))
        TaskFactory(user=user, due_date=date(2026, 12, 15))
        r = auth_client.get(
            f"{self.LIST_URL}?due_date_min=2026-06-01&due_date_max=2026-06-30"
        )
        assert r.data["count"] == 1

    def test_search_title(self, auth_client, user):
        TaskFactory(user=user, title="Buy groceries")
        TaskFactory(user=user, title="Write report")
        r = auth_client.get(f"{self.LIST_URL}?search=groceries")
        assert r.data["count"] == 1

    def test_search_description(self, auth_client, user):
        TaskFactory(user=user, description="This mentions Python")
        TaskFactory(user=user, description="Nothing relevant")
        r = auth_client.get(f"{self.LIST_URL}?search=Python")
        assert r.data["count"] == 1

    def test_ordering_by_due_date(self, auth_client, user):
        TaskFactory(user=user, title="Later", due_date=date(2026, 12, 1))
        TaskFactory(user=user, title="Sooner", due_date=date(2026, 6, 1))
        r = auth_client.get(f"{self.LIST_URL}?ordering=due_date")
        titles = [t["title"] for t in r.data["results"]]
        assert titles[0] == "Sooner"

    def test_ordering_desc(self, auth_client, user):
        TaskFactory(user=user, title="A")
        TaskFactory(user=user, title="Z")
        r = auth_client.get(f"{self.LIST_URL}?ordering=-title")
        titles = [t["title"] for t in r.data["results"]]
        assert titles[0] == "Z"


# ===================================================================
# Task Stats
# ===================================================================
@pytest.mark.django_db
class TestTaskStats:

    URL = "/api/v1/tasks/stats/"

    def test_empty(self, auth_client, user):
        r = auth_client.get(self.URL)
        assert r.status_code == status.HTTP_200_OK
        assert r.data["total"] == 0
        assert r.data["overdue"] == 0

    def test_counts(self, auth_client, user):
        TaskFactory(user=user, status="todo", priority="low")
        TaskFactory(user=user, status="todo", priority="high")
        TaskFactory(user=user, status="in_progress", priority="medium")
        TaskFactory(
            user=user,
            status="todo",
            priority="urgent",
            due_date=date.today() - timedelta(days=1),
        )
        r = auth_client.get(self.URL)
        assert r.data["total"] == 4
        assert r.data["by_status"]["todo"] == 3
        assert r.data["by_status"]["in_progress"] == 1
        assert r.data["by_status"]["done"] == 0
        assert r.data["by_priority"]["low"] == 1
        assert r.data["by_priority"]["urgent"] == 1
        assert r.data["overdue"] == 1

    def test_cross_user_isolation(self, auth_client, other_user):
        TaskFactory(user=other_user)
        r = auth_client.get(self.URL)
        assert r.data["total"] == 0

    def test_unauthenticated(self, api_client):
        r = api_client.get(self.URL)
        assert r.status_code == status.HTTP_401_UNAUTHORIZED
