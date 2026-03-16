from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.admin import TabularInline as UnfoldTabularInline

from app.accounts.models import CompanySettings
from app.handover.models import (
    Handover,
    HandoverAttachment,
    HandoverItem,
    HandoverRecipient,
    ItemCategory,
    Tag,
)


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


class HandoverItemInline(UnfoldTabularInline):
    model = HandoverItem
    extra = 0
    autocomplete_fields = ("category", "assignee", "created_by", "updated_by")
    filter_horizontal = ("tags",)
    fields = (
        "title",
        "category",
        "priority",
        "status",
        "assignee",
        "due_at",
        "description",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("is_deleted", "deleted_at")


class HandoverAttachmentInline(UnfoldTabularInline):
    model = HandoverAttachment
    extra = 0
    autocomplete_fields = ("item", "created_by", "updated_by")
    fields = ("name", "file", "item", "is_deleted", "deleted_at")
    readonly_fields = ("is_deleted", "deleted_at")


class HandoverRecipientInline(UnfoldTabularInline):
    model = HandoverRecipient
    extra = 0
    autocomplete_fields = ("user", "created_by", "updated_by")
    fields = (
        "user",
        "required",
        "confirmed_at",
        "confirmation_type",
        "comment",
        "signature_ref",
        "is_deleted",
        "deleted_at",
    )
    readonly_fields = ("confirmed_at", "confirmation_type", "signature_ref", "is_deleted", "deleted_at")


@admin.register(ItemCategory)
class ItemCategoryAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(Tag)
class TagAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


def _get_company_settings(company) -> CompanySettings | None:
    """Return company settings if present; otherwise None."""
    try:
        return company.settings
    except Exception:
        return None


def _expand_recipients(handover: Handover) -> set[int]:
    """
    Expand recipients from direct users and teams into a set of user IDs.

    Note: Team expansion requires a Team<->User mapping, which is not modeled yet.
    """
    return set(handover.recipients_users.values_list("id", flat=True))


@admin.register(Handover)
class HandoverAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    actions = SoftDeleteAdminMixin.actions + ["deliver_selected", "close_selected"]

    list_display = (
        "subject",
        "company",
        "scope",
        "site",
        "shift",
        "status",
        "starts_at",
        "ends_at",
        "is_deleted",
        "deleted_at",
    )
    list_filter = ("company", "scope", "site", "shift", "status", "is_deleted")
    search_fields = ("subject", "notes", "company__name", "site__name")
    autocomplete_fields = ("company", "site", "shift", "delivered_by", "created_by", "updated_by")
    filter_horizontal = ("recipients_users", "recipients_teams")
    date_hierarchy = "starts_at"
    ordering = ("-starts_at", "-created_at")
    inlines = [HandoverItemInline, HandoverAttachmentInline, HandoverRecipientInline]

    fieldsets = (
        ("Context", {"fields": ("company", "scope", "site", "shift", "starts_at", "ends_at")}),
        ("Content", {"fields": ("subject", "notes")}),
        ("Recipients", {"fields": ("recipients_users", "recipients_teams")}),
        ("Workflow", {"fields": ("status", "delivered_by")}),
        ("Soft Delete", {"fields": ("is_deleted", "deleted_at")}),
        ("Audit", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )
    readonly_fields = ("is_deleted", "deleted_at", "created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        """Auto-fill created_by/updated_by on admin saves."""
        if not change and getattr(obj, "created_by_id", None) is None:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Deliver selected handovers")
    def deliver_selected(self, request, queryset):
        """
        Deliver handovers:
        - Validates scope/site coherence.
        - Enforces CompanySettings.handover_requires_recipients if enabled.
        - Requires at least one item.
        - Creates/updates per-user HandoverRecipient rows from recipients_users.
        """
        delivered_count = 0
        blocked = 0

        with transaction.atomic():
            for handover in queryset.select_related("company", "site").prefetch_related(
                "recipients_users",
                "recipients_teams",
                "items",
            ):
                if handover.status != Handover.Status.DRAFT:
                    blocked += 1
                    continue

                if handover.scope == Handover.Scope.SITE and handover.site_id is None:
                    blocked += 1
                    continue
                if handover.scope == Handover.Scope.GLOBAL and handover.site_id is not None:
                    blocked += 1
                    continue

                settings_obj = _get_company_settings(handover.company)
                recipient_user_ids = _expand_recipients(handover)

                if settings_obj and settings_obj.handover_requires_recipients and not recipient_user_ids:
                    blocked += 1
                    continue

                if not handover.items.exists():
                    blocked += 1
                    continue

                for user_id in recipient_user_ids:
                    HandoverRecipient.all_objects.update_or_create(
                        handover=handover,
                        user_id=user_id,
                        defaults={
                            "required": True,
                            "updated_by": request.user,
                            "created_by": request.user,
                            "is_deleted": False,
                            "deleted_at": None,
                        },
                    )

                handover.status = Handover.Status.DELIVERED
                handover.delivered_by = request.user
                handover.updated_by = request.user
                handover.save(update_fields=["status", "delivered_by", "updated_by", "updated_at"])

                delivered_count += 1

        if delivered_count:
            self.message_user(request, f"Delivered {delivered_count} handover(s).", level=messages.SUCCESS)
        if blocked:
            self.message_user(
                request,
                f"Skipped {blocked} handover(s) (not DRAFT, missing recipients/items, or invalid scope/site).",
                level=messages.WARNING,
            )

    @admin.action(description="Close selected handovers")
    def close_selected(self, request, queryset):
        """
        Close handovers:
        - Only DELIVERED/ACKED can be closed.
        - If CompanySettings.close_requires_all_receipts is True, requires all required receipts to be confirmed.
        """
        closed_count = 0
        blocked = 0

        with transaction.atomic():
            for handover in queryset.select_related("company").prefetch_related("recipient_receipts"):
                if handover.status not in {Handover.Status.DELIVERED, Handover.Status.ACKED}:
                    blocked += 1
                    continue

                settings_obj = _get_company_settings(handover.company)
                if settings_obj and settings_obj.close_requires_all_receipts:
                    required_receipts = handover.recipient_receipts.filter(required=True, is_deleted=False)
                    if required_receipts.exists() and required_receipts.filter(confirmed_at__isnull=True).exists():
                        blocked += 1
                        continue

                handover.status = Handover.Status.CLOSED
                handover.updated_by = request.user
                handover.ends_at = handover.ends_at or timezone.now()
                handover.save(update_fields=["status", "updated_by", "updated_at", "ends_at"])

                closed_count += 1

        if closed_count:
            self.message_user(request, f"Closed {closed_count} handover(s).", level=messages.SUCCESS)
        if blocked:
            self.message_user(
                request,
                f"Skipped {blocked} handover(s) (wrong status or missing required confirmations).",
                level=messages.WARNING,
            )


@admin.register(HandoverItem)
class HandoverItemAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = (
        "title",
        "handover",
        "category",
        "priority",
        "status",
        "assignee",
        "is_deleted",
        "deleted_at",
        "created_at",
    )
    list_filter = ("priority", "status", "category", "is_deleted")
    search_fields = ("title", "description", "handover__subject")
    autocomplete_fields = ("handover", "category", "assignee", "created_by", "updated_by")
    filter_horizontal = ("tags",)
    ordering = ("-created_at",)


@admin.register(HandoverAttachment)
class HandoverAttachmentAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("name", "handover", "item", "file", "is_deleted", "deleted_at", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("name", "handover__subject", "file")
    autocomplete_fields = ("handover", "item", "created_by", "updated_by")
    ordering = ("-created_at",)


@admin.register(HandoverRecipient)
class HandoverRecipientAdmin(SoftDeleteAdminMixin, UnfoldModelAdmin):
    list_display = ("handover", "user", "required", "confirmed_at", "confirmation_type", "is_deleted", "deleted_at")
    list_filter = ("required", "confirmation_type", "is_deleted")
    search_fields = ("handover__subject", "user__username", "user__email")
    autocomplete_fields = ("handover", "user", "created_by", "updated_by")
    ordering = ("-created_at",)
