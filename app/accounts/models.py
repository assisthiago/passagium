from django.conf import settings
from django.db import models

from app.core.models import AuditedModel


class Company(AuditedModel):
    """Tenant entity representing a company."""

    name = models.CharField(verbose_name="nome", max_length=255, unique=True)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"

    def __str__(self) -> str:
        return self.name


class Site(AuditedModel):
    """A physical/logical unit where handovers may occur."""

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="sites",
        db_index=True,
    )
    name = models.CharField(verbose_name="nome", max_length=255)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class Team(AuditedModel):
    """A group of users (optionally tied to a site) for easier recipient selection."""

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="teams",
        db_index=True,
    )
    name = models.CharField(verbose_name="nome", max_length=255)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    site = models.ForeignKey(
        Site,
        verbose_name="unidade",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )

    class Meta:
        verbose_name = "equipe"
        verbose_name_plural = "equipes"
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class TeamMember(AuditedModel):
    """Link table between Team and User to support team-based recipient expansion."""

    team = models.ForeignKey(
        Team,
        verbose_name="equipe",
        on_delete=models.CASCADE,
        related_name="members",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="team_memberships",
        db_index=True,
    )
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    class Meta:
        verbose_name = "membro da equipe"
        verbose_name_plural = "membros da equipe"
        unique_together = (("team", "user"),)
        ordering = ["team__company__name", "team__name", "user__id"]

    def __str__(self) -> str:
        return f"{self.user} ∈ {self.team}"


class Shift(AuditedModel):
    """A configurable shift definition (N shifts per company)."""

    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="shifts",
        db_index=True,
    )
    name = models.CharField(verbose_name="nome", max_length=255)
    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    start_time = models.TimeField(verbose_name="início", null=True, blank=True)
    end_time = models.TimeField(verbose_name="fim", null=True, blank=True)

    sites = models.ManyToManyField(
        Site,
        verbose_name="unidades",
        blank=True,
        related_name="shifts",
    )

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        unique_together = (("company", "name"),)
        ordering = ["company__name", "name"]

    def __str__(self) -> str:
        return f"{self.company} — {self.name}"


class CompanySettings(AuditedModel):
    """Company-level configuration controlling handover behavior and policies."""

    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL", "Global"
        SITE = "SITE", "Site/Unidade"

    class ReceiptPolicy(models.TextChoices):
        CONFIRM_ONLY = "CONFIRM_ONLY", "Apenas confirmação"
        SIGNATURE_REQUIRED = "SIGNATURE_REQUIRED", "Assinatura obrigatória"

    company = models.OneToOneField(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="settings",
    )

    default_scope = models.CharField(
        verbose_name="escopo padrão",
        max_length=16,
        choices=Scope.choices,
        default=Scope.SITE,
        db_index=True,
    )

    handover_requires_recipients = models.BooleanField(
        verbose_name="exige destinatários",
        default=True,
    )
    close_requires_all_receipts = models.BooleanField(
        verbose_name="fechamento exige todos os recibos",
        default=False,
    )

    receipt_policy = models.CharField(
        verbose_name="política de recibo",
        max_length=32,
        choices=ReceiptPolicy.choices,
        default=ReceiptPolicy.CONFIRM_ONLY,
        db_index=True,
    )

    allow_items_without_category = models.BooleanField(
        verbose_name="permitir itens sem categoria",
        default=False,
    )

    class Meta:
        verbose_name = "configuração da empresa"
        verbose_name_plural = "configurações da empresa"

    def __str__(self) -> str:
        return f"Configurações — {self.company}"


class Membership(AuditedModel):
    """Join table linking a user to a company, with optional site/team access constraints."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuário",
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )
    company = models.ForeignKey(
        Company,
        verbose_name="empresa",
        on_delete=models.CASCADE,
        related_name="memberships",
        db_index=True,
    )

    is_active = models.BooleanField(verbose_name="ativo", default=True, db_index=True)

    sites = models.ManyToManyField(
        Site,
        verbose_name="unidades",
        blank=True,
        related_name="memberships",
    )
    teams = models.ManyToManyField(
        Team,
        verbose_name="equipes",
        blank=True,
        related_name="memberships",
    )

    class Meta:
        verbose_name = "vínculo do usuário"
        verbose_name_plural = "vínculos dos usuários"
        unique_together = (("user", "company"),)
        ordering = ["company__name", "user__id"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.company}"
