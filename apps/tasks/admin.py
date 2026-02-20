"""Admin configuration for the tasks app."""

from django.contrib import admin

from .models import Category, Task


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "colour", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "priority", "due_date", "user", "created_at")
    list_filter = ("status", "priority", "user")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
