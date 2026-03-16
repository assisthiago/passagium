from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self) -> "SoftDeleteQuerySet":
        """Return only non-deleted records."""
        return self.filter(is_deleted=False)

    def deleted(self) -> "SoftDeleteQuerySet":
        """Return only soft-deleted records."""
        return self.filter(is_deleted=True)

    def delete(self):
        """
        Soft delete in bulk.

        QuerySet.delete() will mark rows as deleted instead of physically
        removing them from the database.
        """
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def restore(self):
        """Restore soft-deleted records in bulk."""
        return super().update(is_deleted=False, deleted_at=None)


class SoftDeleteManager(models.Manager):
    def get_queryset(self) -> SoftDeleteQuerySet:
        """Default manager: returns only non-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def restore(self):
        """Restore records returned by the default manager (usually a no-op)."""
        return self.get_queryset().restore()


class AllObjectsManager(models.Manager):
    def get_queryset(self) -> SoftDeleteQuerySet:
        """Manager that returns all records, including soft-deleted ones."""
        return SoftDeleteQuerySet(self.model, using=self._db)


class DeletedObjectsManager(models.Manager):
    def get_queryset(self) -> SoftDeleteQuerySet:
        """Manager that returns only soft-deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


class TimeStampedModel(models.Model):
    """Abstract base model providing created/updated timestamps."""

    created_at = models.DateTimeField(verbose_name="criado em", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(verbose_name="atualizado em", auto_now=True, db_index=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract base model implementing soft deletion.

    - objects: only non-deleted records
    - all_objects: all records (including soft-deleted)
    - deleted_objects: only soft-deleted records
    """

    is_deleted = models.BooleanField(verbose_name="excluído", default=False, db_index=True)
    deleted_at = models.DateTimeField(verbose_name="excluído em", null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()
    deleted_objects = DeletedObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        """Soft delete this instance (the only supported deletion behavior)."""
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        """Restore this instance if it was soft-deleted."""
        if self.is_deleted:
            self.is_deleted = False
            self.deleted_at = None
            self.save(update_fields=["is_deleted", "deleted_at"])


class AuditedModel(TimeStampedModel, SoftDeleteModel):
    """Abstract base model adding user-level audit fields on top of timestamps and soft delete."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="criado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
        db_index=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="atualizado por",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
        db_index=True,
    )

    class Meta:
        abstract = True
