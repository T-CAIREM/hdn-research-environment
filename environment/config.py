"""Deployment-specific values shared by environment views and templates."""

from email.utils import parseaddr

from django.conf import settings
from django.db.models import Model


def get_organization_domain(user: Model | None = None) -> str:
    """Use an explicit cloud domain, or derive it from the user's cloud identity."""
    domain = getattr(settings, "CLOUD_RESEARCH_ENVIRONMENTS_ORGANIZATION_DOMAIN", "")
    if not domain:
        identity = getattr(user, "cloud_identity", None)
        domain = getattr(identity, "email", "").rpartition("@")[2]
    return domain.strip().lstrip("@").lower()


def get_support_email() -> str:
    """Return a bare support address, accepting the host's named email settings."""
    address = (
        getattr(settings, "SUPPORT_EMAIL", "")
        or getattr(settings, "CONTACT_EMAIL", "")
        or settings.DEFAULT_FROM_EMAIL
    )
    return parseaddr(address)[1]
