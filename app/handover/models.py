from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app.accounts.models import Company, Shift, Site, Team
from app.core.models import AuditedModel


class ItemCategory(AuditedModel):
    """Company-scoped category used to classify handover items."""

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="item_categories",
        db_index=True,
    )
    name = models.CharField(verbose_name="nome", max_length=120)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "categoria de item"
        verbose_name_plural = "categorias de itens"
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class Tag(AuditedModel):
    """Company-scoped tag used for search and quick filtering."""

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="tags",
        db_index=True,
    )
    name = models.CharField(verbose_name="nome", max_length=80)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "tag"
        verbose_name_plural = "tags"
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class Handover(AuditedModel):
    """A handover record grouping items, attachments, recipients, and audit trail."""

    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        SITE = "SITE", "Site/Unidade"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        DELIVERED = "DELIVERED", "Entregue"
        ACKED = "ACKED", "Recebido/Confirmado"
        CLOSED = "CLOSED", "Fechado"

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="handovers",
        db_index=True,
    )

    scope = models.CharField(
        verbose_name="escopo",
        max_length=16,
        choices=Scope.choices,
        default=Scope.SITE,
        db_index=True,
    )
    site = models.ForeignKey(
        Site,
        verbose_name="unidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handovers",
        db_index=True,
    )

    shift = models.ForeignKey(
        Shift,
        verbose_name="turno",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handovers",
        db_index=True,
    )

    starts_at = models.DateTimeField(verbose_name="início", default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(verbose_name="fim", null=True, blank=True, db_index=True)

    subject = models.CharField(verbose_name="assunto", max_length=255)
    notes = models.TextField(verbose_name="observações", blank=True)

    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="entregue por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handovers_delivered",
        db_index=True,
    )

    status = models.CharField(
        verbose_name="status",
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    recipients_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="destinatários (usuários)",
        blank=True,
        related_name="handovers_to_receive_users",
    )
    recipients_teams = models.ManyToManyField(
        Team,
        verbose_name="destinatários (equipes)",
        blank=True,
        related_name="handovers_to_receive_teams",
    )

    class Meta:
        verbose_name = "passagem de plantão"
        verbose_name_plural = "passagens de plantão"
        ordering = ["-starts_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.company} — {self.subject} ({self.starts_at:%Y-%m-%d})"

    def clean(self):
        """Validate scope/site coherence and company-safe FK relations."""
        errors: dict[str, list[str]] = {}

        if self.scope == self.Scope.SITE and self.site_id is None:
            errors.setdefault("site", []).append("Obrigatório quando o escopo é Site/Unidade.")

        if self.scope == self.Scope.GLOBAL and self.site_id is not None:
            errors.setdefault("site", []).append("Deve ficar vazio quando o escopo é Global.")

        if self.site_id and self.company_id and self.site.company_id != self.company_id:
            errors.setdefault("site", []).append("A unidade pertence a outra empresa.")

        if self.shift_id and self.company_id and self.shift.company_id != self.company_id:
            errors.setdefault("shift", []).append("O turno pertence a outra empresa.")

        if errors:
            raise ValidationError(errors)


class HandoverItem(AuditedModel):
    """A structured item belonging to a handover (incident, pending task, notice, etc.)."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Baixa"
        MED = "MED", "Média"
        HIGH = "HIGH", "Alta"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto/Pendente"
        DONE = "DONE", "Resolvido"
        INFO = "INFO", "Informativo"

    handover = models.ForeignKey(
        Handover,
        verbose_name="passagem de plantão",
        on_delete=models.CASCADE,
        related_name="items",
        db_index=True,
    )

    category = models.ForeignKey(
        ItemCategory,
        verbose_name="categoria",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
        db_index=True,
    )

    title = models.CharField(verbose_name="título", max_length=255)
    description = models.TextField(verbose_name="descrição", blank=True)

    priority = models.CharField(
        verbose_name="prioridade",
        max_length=8,
        choices=Priority.choices,
        default=Priority.MED,
        db_index=True,
    )
    status = models.CharField(
        verbose_name="status",
        max_length=8,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="responsável",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handover_items_assigned",
        db_index=True,
    )

    due_at = models.DateTimeField(verbose_name="prazo", null=True, blank=True, db_index=True)

    tags = models.ManyToManyField(Tag, verbose_name="tags", blank=True, related_name="items")

    class Meta:
        verbose_name = "item da passagem"
        verbose_name_plural = "itens da passagem"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        """Validate company-safe relations for category."""
        errors: dict[str, list[str]] = {}

        if self.category_id and self.handover_id:
            if self.category.company_id != self.handover.company_id:
                errors.setdefault("category", []).append("A categoria pertence a outra empresa.")

        if errors:
            raise ValidationError(errors)


class HandoverAttachment(AuditedModel):
    """File evidence attached to a handover and optionally to a specific item."""

    handover = models.ForeignKey(
        Handover,
        verbose_name="passagem de plantão",
        on_delete=models.CASCADE,
        related_name="attachments",
        db_index=True,
    )
    item = models.ForeignKey(
        HandoverItem,
        verbose_name="item",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="attachments",
        db_index=True,
    )

    file = models.FileField(verbose_name="arquivo", upload_to="handover_attachments/")
    name = models.CharField(verbose_name="nome", max_length=255, blank=True)

    class Meta:
        verbose_name = "anexo"
        verbose_name_plural = "anexos"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name or self.file.name

    def clean(self):
        """Validate attachment consistency with item/handover."""
        errors: dict[str, list[str]] = {}

        if self.item_id and self.handover_id:
            if self.item.handover_id != self.handover_id:
                errors.setdefault("item", []).append("O item selecionado não pertence à mesma passagem.")

        if errors:
            raise ValidationError(errors)


class HandoverRecipient(AuditedModel):
    """Per-user receipt/acknowledgement record, prepared for future signature support."""

    class ConfirmationType(models.TextChoices):
        CONFIRM = "CONFIRM", "Confirmação"
        SIGNATURE = "SIGNATURE", "Assinatura"

    handover = models.ForeignKey(
        Handover,
        verbose_name="passagem de plantão",
        on_delete=models.CASCADE,
        related_name="recipient_receipts",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="handover_receipts",
        db_index=True,
    )

    required = models.BooleanField(verbose_name="obrigatório", default=True)

    confirmed_at = models.DateTimeField(verbose_name="confirmado em", null=True, blank=True, db_index=True)
    confirmation_type = models.CharField(
        verbose_name="tipo de confirmação",
        max_length=16,
        choices=ConfirmationType.choices,
        default=ConfirmationType.CONFIRM,
    )

    comment = models.TextField(verbose_name="comentário", blank=True)

    signature_ref = models.CharField(verbose_name="referência de assinatura", max_length=255, blank=True)

    class Meta:
        verbose_name = "recibo do destinatário"
        verbose_name_plural = "recibos dos destinatários"
        unique_together = (("handover", "user"),)
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.handover} — {self.user}"
