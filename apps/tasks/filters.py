"""
django-filter FilterSet for Task queryset filtering.

Supports filtering by:
  - status (exact match or comma-separated list)
  - priority (exact match or comma-separated list)
  - category UUID
  - overdue flag (boolean — computed from due_date < today & status ≠ done)
  - due_date range (min / max)
"""

from datetime import date

from django.db.models import Q
from django_filters import rest_framework as filters

from .models import Task


class TaskFilter(filters.FilterSet):
    """
    Filterable fields exposed as query parameters on GET /tasks/.

    Examples:
        ?status=todo,in_progress
        ?priority=high,urgent
        ?category=<uuid>
        ?overdue=true
        ?due_date_min=2026-01-01&due_date_max=2026-12-31
    """

    status = filters.CharFilter(method="filter_csv_field")
    priority = filters.CharFilter(method="filter_csv_field")
    category = filters.UUIDFilter(field_name="category__id")
    overdue = filters.BooleanFilter(method="filter_overdue")
    due_date_min = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_max = filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["status", "priority", "category", "overdue", "due_date_min", "due_date_max"]

    # ----- helpers -----

    def filter_csv_field(self, queryset, name, value):
        """Allow comma-separated values, e.g. ?status=todo,in_progress."""
        values = [v.strip() for v in value.split(",") if v.strip()]
        if values:
            return queryset.filter(**{f"{name}__in": values})
        return queryset

    def filter_overdue(self, queryset, name, value):
        """
        ?overdue=true  → tasks with due_date < today AND status ≠ done
        ?overdue=false → everything else
        """
        today = date.today()
        overdue_q = Q(due_date__lt=today) & ~Q(status=Task.Status.DONE)
        if value:
            return queryset.filter(overdue_q)
        return queryset.exclude(overdue_q)
