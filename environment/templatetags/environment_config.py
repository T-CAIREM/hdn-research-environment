"""Expose deployment settings without requiring a host context processor."""

from django import template
from django.conf import settings
from django.db.models import Model

from environment.config import get_organization_domain, get_support_email

register = template.Library()


@register.simple_tag
def research_environment_config(user: Model | None = None) -> dict[str, str]:
    """Return branding and cloud-domain configuration for the current deployment."""
    return {
        "organization_domain": get_organization_domain(user),
        "site_name": settings.SITE_NAME,
        "support_email": get_support_email(),
    }
