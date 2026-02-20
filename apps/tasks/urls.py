"""
Tasks app URL configuration.

Uses DRF Routers for automatic URL generation from ViewSets.
All endpoints are mounted under /api/v1/ by the root URL config.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
]
