from django.contrib import admin, messages
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from app.accounts.models import Company, CompanySettings, Membership, Shift, Site, Team


class SoftDeleteAdminMixin:
    """Admin mixin that exposes soft-deleted rows and provides a restore action."""

    actions = ["restore_selected"]

    def get_queryset(self, request):
        """Use all_objects so admins can view and restore soft-deleted records."""
        qs = super().get_queryset(request)
        model = getattr(self, "model", None)
        if model is not None and hasattr(model, "all_objects"):
            return model.all_objects.all()
        return qs

    @admin.action(description="Restore selected (soft-deleted) records")
    def restore_selected(self, request, queryset):
        updated = queryset.restore()
        self.message_user(
            request,
            f"Restored {updated} record(s).",
            level=messages.SUCCESS,
        )


class CompanySettingsInline(UnfoldTabularInline):
    model = CompanySettings
    extra = 0
    can_delete = False


@admin.register(Company)
class CompanyAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "is_active", "is_deleted", "deleted_at", "created_at", "updated_at")
    list_filter = ("is_active", "is_deleted", "created_at")
    search_fields = ("name",)
    inlines = [CompanySettingsInline]
    ordering = ("name",)


@admin.register(Site)
class SiteAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(Team)
class TeamAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "company", "site", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "site", "is_active", "is_deleted")
    search_fields = ("name", "company__name", "site__name")
    autocomplete_fields = ("company", "site")
    ordering = ("company__name", "name")


@admin.register(Shift)
class ShiftAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "company", "is_active", "start_time", "end_time", "is_deleted", "deleted_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    filter_horizontal = ("sites",)
    ordering = ("company__name", "name")


@admin.register(CompanySettings)
class CompanySettingsAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = (
        "company",
        "default_scope",
        "handover_requires_recipients",
        "close_requires_all_receipts",
        "receipt_policy",
        "allow_items_without_category",
        "is_deleted",
        "deleted_at",
    )
    list_filter = (
        "default_scope",
        "receipt_policy",
        "handover_requires_recipients",
        "close_requires_all_receipts",
        "is_deleted",
    )
    search_fields = ("company__name",)
    autocomplete_fields = ("company",)


@admin.register(Membership)
class MembershipAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("user", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("user__username", "user__email", "company__name")
    autocomplete_fields = ("user", "company")
    filter_horizontal = ("sites", "teams")
    ordering = ("company__name", "user__id")
