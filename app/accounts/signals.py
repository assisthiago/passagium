from django.db.models.signals import post_save
from django.dispatch import receiver

from app.accounts.models import Company, CompanySettings


@receiver(post_save, sender=Company)
def ensure_company_settings(sender, instance: Company, created: bool, **kwargs):
    """Ensure a CompanySettings row exists for every Company."""
    if not created:
        return

    # Use all_objects to consider soft-deleted rows as well.
    CompanySettings.all_objects.get_or_create(company=instance)
