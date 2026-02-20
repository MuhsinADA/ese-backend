"""
ViewSets for Task and Category CRUD, plus a Task statistics endpoint.

Key enterprise patterns:
  - All querysets are scoped to request.user (no cross-user access)
  - Object-level IsOwner permission enforced on retrieve/update/delete
  - Category annotated with task_count for the list view
  - Task stats aggregated server-side for the dashboard
"""

from datetime import date

from django.db.models import Count, Q

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from .filters import TaskFilter
from .models import Category, Task
from .permissions import IsOwner
from .serializers import CategorySerializer, TaskSerializer, TaskStatsSerializer


# ---------------------------------------------------------------------------
# Category ViewSet
# ---------------------------------------------------------------------------
class CategoryViewSet(viewsets.ModelViewSet):
    """
    CRUD for user-owned categories.

    list   → GET    /api/v1/categories/
    create → POST   /api/v1/categories/
    read   → GET    /api/v1/categories/{id}/
    update → PATCH  /api/v1/categories/{id}/
    delete → DELETE /api/v1/categories/{id}/
    """

    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsOwner]
    # Disable PUT — only PATCH for partial updates (enterprise convention)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        """Return only the authenticated user's categories, with task count."""
        return (
            Category.objects.filter(user=self.request.user)
            .annotate(task_count=Count("tasks"))
            .order_by("name")
        )

    def perform_create(self, serializer):
        """Automatically assign the authenticated user as the owner."""
        serializer.save(user=self.request.user)


# ---------------------------------------------------------------------------
# Task ViewSet
# ---------------------------------------------------------------------------
class TaskViewSet(viewsets.ModelViewSet):
    """
    CRUD for user-owned tasks, with filtering, search, ordering, and pagination.

    list   → GET    /api/v1/tasks/           (filterable, searchable, sortable)
    create → POST   /api/v1/tasks/
    read   → GET    /api/v1/tasks/{id}/
    update → PATCH  /api/v1/tasks/{id}/
    delete → DELETE /api/v1/tasks/{id}/
    stats  → GET    /api/v1/tasks/stats/

    Query parameters:
      ?status=todo,in_progress    — filter by status (CSV)
      ?priority=high,urgent       — filter by priority (CSV)
      ?category=<uuid>            — filter by category
      ?overdue=true               — filter overdue tasks
      ?due_date_min=2026-01-01    — due date range (min)
      ?due_date_max=2026-12-31    — due date range (max)
      ?search=keyword             — search title + description
      ?ordering=-due_date         — sort (prefix - for desc)
      ?page=1&page_size=10        — pagination
    """

    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    # Filtering / search / ordering configured at view level
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TaskFilter
    search_fields = ["title", "description"]
    ordering_fields = [
        "title",
        "status",
        "priority",
        "due_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]  # default ordering

    def get_queryset(self):
        """Return only the authenticated user's tasks."""
        return Task.objects.filter(user=self.request.user).select_related("category")

    def perform_create(self, serializer):
        """Automatically assign the authenticated user as the owner."""
        serializer.save(user=self.request.user)

    # ----- Custom action: stats -----
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request):
        """
        GET /api/v1/tasks/stats/

        Returns aggregate counts for the authenticated user's tasks:
          - total count
          - count by status
          - count by priority
          - overdue count
        """
        qs = self.get_queryset()

        # Total
        total = qs.count()

        # By status
        status_counts = dict(
            qs.values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )
        # Ensure all statuses are present
        by_status = {s.value: status_counts.get(s.value, 0) for s in Task.Status}

        # By priority
        priority_counts = dict(
            qs.values_list("priority")
            .annotate(count=Count("id"))
            .values_list("priority", "count")
        )
        by_priority = {p.value: priority_counts.get(p.value, 0) for p in Task.Priority}

        # Overdue
        today = date.today()
        overdue = qs.filter(due_date__lt=today).exclude(status=Task.Status.DONE).count()

        data = {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "overdue": overdue,
        }
        serializer = TaskStatsSerializer(data)
        return Response(serializer.data)
