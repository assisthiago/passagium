from django.conf import settings
from django.db import models
from django.utils import timezone

from app.accounts.models import Company, Shift, Site, Team
from app.core.models import AuditedModel


class ItemCategory(AuditedModel):
    """Company-scoped category used to classify handover items."""

    company = models.ForeignKey(
        Company, verbose_name="empresa", on_delete=models.CASCADE, related_name="item_categories", db_index=True
    )
    name = models.CharField(verbose_name="nome", max_length=120)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class Tag(AuditedModel):
    """Company-scoped tag used for search and quick filtering."""

    company = models.ForeignKey(
        Company, verbose_name="empresa", on_delete=models.CASCADE, related_name="tags", db_index=True
    )
    name = models.CharField(verbose_name="nome", max_length=80)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class Handover(AuditedModel):
    """A handover record grouping items, attachments, recipients, and audit trail."""

    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        SITE = "SITE", "Site/Unit"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        DELIVERED = "DELIVERED", "Delivered"
        ACKED = "ACKED", "Acknowledged"
        CLOSED = "CLOSED", "Closed"

    company = models.ForeignKey(
        Company, verbose_name="empresa", on_delete=models.CASCADE, related_name="handovers", db_index=True
    )

    scope = models.CharField(
        verbose_name="escopo", max_length=16, choices=Scope.choices, default=Scope.SITE, db_index=True
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

    starts_at = models.DateTimeField(verbose_name="iniciado em", default=timezone.now, db_index=True)
    ends_at = models.DateTimeField(verbose_name="finalizado em", null=True, blank=True, db_index=True)

    subject = models.CharField(verbose_name="assunto", max_length=255)
    notes = models.TextField(verbose_name="notas", blank=True)

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
        verbose_name="status", max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
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
        ordering = ["-starts_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.company} — {self.subject} ({self.starts_at:%Y-%m-%d})"


class HandoverItem(AuditedModel):
    """A structured item belonging to a handover (incident, pending task, notice, etc.)."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MED = "MED", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open/Pending"
        DONE = "DONE", "Done"
        INFO = "INFO", "Info-only"

    handover = models.ForeignKey(
        Handover, verbose_name="entrega", on_delete=models.CASCADE, related_name="items", db_index=True
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
        verbose_name="prioridade", max_length=8, choices=Priority.choices, default=Priority.MED, db_index=True
    )
    status = models.CharField(
        verbose_name="status", max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True
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

    tags = models.ManyToManyField(Tag, verbose_name="etiquetas", blank=True, related_name="items")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class HandoverAttachment(AuditedModel):
    """File evidence attached to a handover and optionally to a specific item."""

    handover = models.ForeignKey(
        Handover, verbose_name="entrega", on_delete=models.CASCADE, related_name="attachments", db_index=True
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
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name or self.file.name


class HandoverRecipient(AuditedModel):
    """Per-user receipt/acknowledgement record, prepared for future signature support."""

    class ConfirmationType(models.TextChoices):
        CONFIRM = "CONFIRM", "Confirm"
        SIGNATURE = "SIGNATURE", "Signature"

    handover = models.ForeignKey(
        Handover, verbose_name="entrega", on_delete=models.CASCADE, related_name="recipient_receipts", db_index=True
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

    signature_ref = models.CharField(verbose_name="referência da assinatura", max_length=255, blank=True)

    class Meta:
        unique_together = (("handover", "user"),)
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.handover} — {self.user}"
