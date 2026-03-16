from __future__ import annotations

from app.accounts.models import (
    Company,
    CompanySettings,
    Membership,
    Shift,
    Site,
    Team,
    TeamMember,
)
from app.core.admin import BaseModelAdmin, TabularInline, admin


class CompanySettingsInline(TabularInline):
    model = CompanySettings
    extra = 0
    can_delete = False


@admin.register(Company)
class CompanyAdmin(BaseModelAdmin):
    list_display = ("name", "is_active", "is_deleted", "deleted_at", "created_at", "updated_at")
    list_filter = ("is_active", "is_deleted", "created_at")
    search_fields = ("name",)
    inlines = [CompanySettingsInline]
    ordering = ("name",)


@admin.register(Site)
class SiteAdmin(BaseModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(Team)
class TeamAdmin(BaseModelAdmin):
    list_display = ("name", "company", "site", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "site", "is_active", "is_deleted")
    search_fields = ("name", "company__name", "site__name")
    autocomplete_fields = ("company", "site")
    ordering = ("company__name", "name")


@admin.register(TeamMember)
class TeamMemberAdmin(BaseModelAdmin):
    list_display = ("team", "user", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("team__company", "team", "is_active", "is_deleted")
    search_fields = ("team__name", "team__company__name", "user__username", "user__email")
    autocomplete_fields = ("team", "user", "created_by", "updated_by")
    ordering = ("team__company__name", "team__name", "user__id")


@admin.register(Shift)
class ShiftAdmin(BaseModelAdmin):
    list_display = ("name", "company", "is_active", "start_time", "end_time", "is_deleted", "deleted_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    filter_horizontal = ("sites",)
    ordering = ("company__name", "name")


@admin.register(CompanySettings)
class CompanySettingsAdmin(BaseModelAdmin):
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
class MembershipAdmin(BaseModelAdmin):
    list_display = ("user", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("user__username", "user__email", "company__name")
    autocomplete_fields = ("user", "company")
    filter_horizontal = ("sites", "teams")
    ordering = ("company__name", "user__id")
