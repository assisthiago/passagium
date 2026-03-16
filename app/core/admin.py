from __future__ import annotations

from django.contrib import admin as django_admin
from django.contrib import messages as django_messages
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

admin = django_admin
messages = django_messages
TabularInline = UnfoldTabularInline


class BaseModelAdmin(UnfoldModelAdmin):
    """Base Unfold admin that enforces soft-delete visibility and audit fields population."""

    actions = ["restore_selected"]

    def get_queryset(self, request):
        """Use all_objects so admins can view and restore soft-deleted records."""
        qs = super().get_queryset(request)
        model = getattr(self, "model", None)
        if model is not None and hasattr(model, "all_objects"):
            return model.all_objects.all()
        return qs

    def save_model(self, request, obj, form, change):
        """Auto-fill created_by/updated_by on admin saves."""
        if hasattr(obj, "created_by_id") and not change and getattr(obj, "created_by_id", None) is None:
            obj.created_by = request.user
        if hasattr(obj, "updated_by_id"):
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Restaurar selecionados (soft delete)")
    def restore_selected(self, request, queryset):
        """Restore soft-deleted records."""
        updated = queryset.restore()
        self.message_user(
            request,
            f"Restaurados {updated} registro(s).",
            level=messages.SUCCESS,
        )
