from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.accounts.models import CompanySettings, TeamMember
from app.core.admin import BaseModelAdmin, TabularInline, admin, messages
from app.handover.models import (
    Handover,
    HandoverAttachment,
    HandoverItem,
    HandoverRecipient,
    ItemCategory,
    Tag,
)


class HandoverItemInline(TabularInline):
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


class HandoverAttachmentInline(TabularInline):
    model = HandoverAttachment
    extra = 0
    autocomplete_fields = ("item", "created_by", "updated_by")
    fields = ("name", "file", "item", "is_deleted", "deleted_at")
    readonly_fields = ("is_deleted", "deleted_at")


class HandoverRecipientInline(TabularInline):
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
    readonly_fields = ("is_deleted", "deleted_at")


def get_company_settings(company) -> CompanySettings | None:
    """Return company settings if present; otherwise None."""
    try:
        return company.settings
    except Exception:
        return None


def expand_recipient_user_ids(handover: Handover) -> set[int]:
    """Expand recipients from direct users and teams into a unique set of user IDs."""
    user_ids: set[int] = set(handover.recipients_users.values_list("id", flat=True))

    team_ids = list(handover.recipients_teams.values_list("id", flat=True))
    if team_ids:
        team_user_ids = TeamMember.objects.filter(
            team_id__in=team_ids,
            is_active=True,
            is_deleted=False,
        ).values_list("user_id", flat=True)
        user_ids.update(team_user_ids)

    return user_ids


def should_set_acked_status(handover: Handover, settings_obj: CompanySettings | None) -> bool:
    """
    Decide whether the handover should move to ACKED after confirming receipts.

    Policy:
    - If close_requires_all_receipts is True: ACKED only when all required receipts are confirmed.
    - Otherwise: ACKED when at least one receipt is confirmed.
    """
    required_receipts = handover.recipient_receipts.filter(is_deleted=False, required=True)

    if settings_obj and settings_obj.close_requires_all_receipts:
        if not required_receipts.exists():
            return False
        return not required_receipts.filter(confirmed_at__isnull=True).exists()

    return handover.recipient_receipts.filter(is_deleted=False, confirmed_at__isnull=False).exists()


def remove_invalid_team_recipients(handover: Handover) -> int:
    """Remove team recipients that do not belong to the handover company."""
    invalid_teams = handover.recipients_teams.exclude(company_id=handover.company_id)
    removed_count = invalid_teams.count()
    if removed_count:
        handover.recipients_teams.remove(*invalid_teams)
    return removed_count


def remove_invalid_item_tags(items: list[HandoverItem]) -> int:
    """Remove tags that do not belong to the handover company for each item."""
    removed_total = 0
    for item in items:
        company_id = item.handover.company_id
        invalid_tags = item.tags.exclude(company_id=company_id)
        invalid_count = invalid_tags.count()
        if invalid_count:
            item.tags.remove(*invalid_tags)
            removed_total += invalid_count
    return removed_total


@admin.register(ItemCategory)
class ItemCategoryAdmin(BaseModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(Tag)
class TagAdmin(BaseModelAdmin):
    list_display = ("name", "company", "is_active", "is_deleted", "deleted_at", "created_at")
    list_filter = ("company", "is_active", "is_deleted")
    search_fields = ("name", "company__name")
    autocomplete_fields = ("company",)
    ordering = ("company__name", "name")


@admin.register(Handover)
class HandoverAdmin(BaseModelAdmin):
    actions = BaseModelAdmin.actions + [
        "deliver_selected_handovers",
        "confirm_pending_receipts_for_selected_handovers",
        "close_selected_handovers",
    ]

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
        ("Contexto", {"fields": ("company", "scope", "site", "shift", "starts_at", "ends_at")}),
        ("Conteúdo", {"fields": ("subject", "notes")}),
        ("Destinatários", {"fields": ("recipients_users", "recipients_teams")}),
        ("Fluxo", {"fields": ("status", "delivered_by")}),
        ("Exclusão", {"fields": ("is_deleted", "deleted_at")}),
        ("Auditoria", {"fields": ("created_by", "updated_by", "created_at", "updated_at")}),
    )
    readonly_fields = ("is_deleted", "deleted_at", "created_at", "updated_at", "status")

    def get_readonly_fields(self, request, obj=None):
        """Lock operational fields after delivery to prevent breaking the workflow."""
        readonly_fields = list(super().get_readonly_fields(request, obj))

        if obj and obj.status != Handover.Status.DRAFT:
            locked_fields = [
                "scope",
                "site",
                "shift",
                "starts_at",
                "ends_at",
                "recipients_users",
                "recipients_teams",
                "delivered_by",
            ]
            for field in locked_fields:
                if field not in readonly_fields:
                    readonly_fields.append(field)

        return tuple(readonly_fields)

    def save_related(self, request, form, formsets, change):
        """Enforce company-safe M2M relations after admin saves relations."""
        super().save_related(request, form, formsets, change)

        handover: Handover = form.instance
        removed_teams = remove_invalid_team_recipients(handover)
        if removed_teams:
            self.message_user(
                request,
                f"Foram removidas {removed_teams} equipe(s) de destinatários por pertencerem a outra empresa.",
                level=messages.WARNING,
            )

        items = list(handover.items.all().select_related("handover"))
        removed_tags = remove_invalid_item_tags(items)
        if removed_tags:
            self.message_user(
                request,
                f"Foram removidas {removed_tags} tag(s) de itens por pertencerem a outra empresa.",
                level=messages.WARNING,
            )

    @admin.action(description="Entregar passagens selecionadas")
    def deliver_selected_handovers(self, request, queryset):
        """
        Deliver handovers:
        - Validates scope/site coherence.
        - Enforces CompanySettings.handover_requires_recipients if enabled.
        - Requires at least one item.
        - Creates/updates per-user HandoverRecipient rows from recipients_users + teams.
        """
        delivered_count = 0
        blocked_count = 0

        with transaction.atomic():
            for handover in queryset.select_related("company", "site").prefetch_related(
                "recipients_users",
                "recipients_teams",
                "items",
            ):
                if handover.status != Handover.Status.DRAFT:
                    blocked_count += 1
                    continue

                try:
                    handover.full_clean()
                except Exception:
                    blocked_count += 1
                    continue

                settings_obj = get_company_settings(handover.company)
                recipient_user_ids = expand_recipient_user_ids(handover)

                if settings_obj and settings_obj.handover_requires_recipients and not recipient_user_ids:
                    blocked_count += 1
                    continue

                if not handover.items.exists():
                    blocked_count += 1
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
            self.message_user(request, f"Entregues {delivered_count} passagem(ns).", level=messages.SUCCESS)
        if blocked_count:
            self.message_user(
                request,
                f"Ignoradas {blocked_count} passagem(ns) (dados inválidos, sem destinatários/itens, ou status diferente de rascunho).",
                level=messages.WARNING,
            )

    @admin.action(description="Confirmar recebimentos pendentes (todas as pessoas) nas passagens selecionadas")
    def confirm_pending_receipts_for_selected_handovers(self, request, queryset):
        """
        Confirm pending receipts for all recipients of the selected handovers.
        This is useful as an operational shortcut in early MVP stages.
        """
        updated_total = 0
        now = timezone.now()

        with transaction.atomic():
            for handover in queryset.select_related("company").prefetch_related("recipient_receipts"):
                pending_receipts = handover.recipient_receipts.filter(is_deleted=False, confirmed_at__isnull=True)
                updated_count = pending_receipts.update(
                    confirmed_at=now,
                    confirmation_type=HandoverRecipient.ConfirmationType.CONFIRM,
                    updated_by=request.user,
                )
                updated_total += updated_count

                settings_obj = get_company_settings(handover.company)
                if handover.status in {Handover.Status.DELIVERED, Handover.Status.ACKED} and should_set_acked_status(
                    handover, settings_obj
                ):
                    if handover.status != Handover.Status.ACKED:
                        handover.status = Handover.Status.ACKED
                        handover.updated_by = request.user
                        handover.save(update_fields=["status", "updated_by", "updated_at"])

        self.message_user(
            request,
            f"Confirmados {updated_total} recebimento(s) pendente(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="Fechar passagens selecionadas")
    def close_selected_handovers(self, request, queryset):
        """
        Close handovers:
        - Only DELIVERED/ACKED can be closed.
        - If CompanySettings.close_requires_all_receipts is True, requires all required receipts to be confirmed.
        """
        closed_count = 0
        blocked_count = 0

        with transaction.atomic():
            for handover in queryset.select_related("company").prefetch_related("recipient_receipts"):
                if handover.status not in {Handover.Status.DELIVERED, Handover.Status.ACKED}:
                    blocked_count += 1
                    continue

                settings_obj = get_company_settings(handover.company)
                if settings_obj and settings_obj.close_requires_all_receipts:
                    required_receipts = handover.recipient_receipts.filter(required=True, is_deleted=False)
                    if required_receipts.exists() and required_receipts.filter(confirmed_at__isnull=True).exists():
                        blocked_count += 1
                        continue

                handover.status = Handover.Status.CLOSED
                handover.updated_by = request.user
                handover.ends_at = handover.ends_at or timezone.now()
                handover.save(update_fields=["status", "updated_by", "updated_at", "ends_at"])
                closed_count += 1

        if closed_count:
            self.message_user(request, f"Fechadas {closed_count} passagem(ns).", level=messages.SUCCESS)
        if blocked_count:
            self.message_user(
                request,
                f"Ignoradas {blocked_count} passagem(ns) (status inválido ou faltam confirmações obrigatórias).",
                level=messages.WARNING,
            )


@admin.register(HandoverItem)
class HandoverItemAdmin(BaseModelAdmin):
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

    def save_related(self, request, form, formsets, change):
        """Enforce company-safe tags after item relation saves."""
        super().save_related(request, form, formsets, change)
        item: HandoverItem = form.instance
        removed_tags = remove_invalid_item_tags([item])
        if removed_tags:
            self.message_user(
                request,
                f"Foram removidas {removed_tags} tag(s) por pertencerem a outra empresa.",
                level=messages.WARNING,
            )


@admin.register(HandoverAttachment)
class HandoverAttachmentAdmin(BaseModelAdmin):
    list_display = ("name", "handover", "item", "file", "is_deleted", "deleted_at", "created_at")
    list_filter = ("is_deleted",)
    search_fields = ("name", "handover__subject", "file")
    autocomplete_fields = ("handover", "item", "created_by", "updated_by")
    ordering = ("-created_at",)


@admin.register(HandoverRecipient)
class HandoverRecipientAdmin(BaseModelAdmin):
    actions = BaseModelAdmin.actions + ["confirm_selected_receipts"]

    list_display = ("handover", "user", "required", "confirmed_at", "confirmation_type", "is_deleted", "deleted_at")
    list_filter = ("required", "confirmation_type", "is_deleted")
    search_fields = ("handover__subject", "user__username", "user__email")
    autocomplete_fields = ("handover", "user", "created_by", "updated_by")
    ordering = ("-created_at",)

    @admin.action(description="Confirmar recebimento (selecionados)")
    def confirm_selected_receipts(self, request, queryset):
        """Confirm selected receipts and update related handover statuses when applicable."""
        now = timezone.now()

        receipts_to_confirm = queryset.filter(is_deleted=False, confirmed_at__isnull=True).select_related(
            "handover",
            "handover__company",
        )
        handover_ids = list(receipts_to_confirm.values_list("handover_id", flat=True).distinct())

        updated_receipts = receipts_to_confirm.update(
            confirmed_at=now,
            confirmation_type=HandoverRecipient.ConfirmationType.CONFIRM,
            updated_by=request.user,
        )

        if not handover_ids:
            self.message_user(
                request,
                f"Confirmados {updated_receipts} recebimento(s).",
                level=messages.SUCCESS,
            )
            return

        handovers = (
            Handover.all_objects.filter(id__in=handover_ids, is_deleted=False)
            .select_related("company")
            .prefetch_related("recipient_receipts")
        )

        updated_handovers = 0
        for handover in handovers:
            if handover.status not in {Handover.Status.DELIVERED, Handover.Status.ACKED}:
                continue

            settings_obj = get_company_settings(handover.company)
            if should_set_acked_status(handover, settings_obj) and handover.status != Handover.Status.ACKED:
                handover.status = Handover.Status.ACKED
                handover.updated_by = request.user
                handover.save(update_fields=["status", "updated_by", "updated_at"])
                updated_handovers += 1

        self.message_user(
            request,
            f"Confirmados {updated_receipts} recebimento(s). Passagens atualizadas: {updated_handovers}.",
            level=messages.SUCCESS,
        )
