"""Deployment-specific values shared by environment views and templates."""

import logging
from email.utils import parseaddr

from django.conf import settings
from django.db.models import Model

logger = logging.getLogger(__name__)

_TRUE_STRINGS = {"1", "true", "yes", "on"}

EXPIRED_ACCESS_ENFORCEMENT_OFF = "off"
EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN = "dry_run"
EXPIRED_ACCESS_ENFORCEMENT_ENFORCE = "enforce"
_EXPIRED_ACCESS_ENFORCEMENT_MODES = (
    EXPIRED_ACCESS_ENFORCEMENT_OFF,
    EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN,
    EXPIRED_ACCESS_ENFORCEMENT_ENFORCE,
)


def _setting_enabled(name: str, default: bool = False) -> bool:
    """Read a boolean setting, accepting the strings an env-driven host may pass."""
    value = getattr(settings, name, default)
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    return bool(value)


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


def draft_workbenches_enabled() -> bool:
    """Whether researchers may attach their own draft projects to new workbenches.

    Off by default: draft workbenches mount the draft's files read-write, so a
    deployment opts in explicitly.
    """
    return _setting_enabled("CLOUD_RESEARCH_ENVIRONMENTS_ENABLE_DRAFT_WORKBENCHES")


def get_expired_access_enforcement() -> str:
    """How the expired-access tasks act: "off", "dry_run" (default) or "enforce".

    "dry_run" logs every workbench an enforcing run would stop or destroy and
    changes nothing (no stop, no delete, no email), so the first run on a
    deployment is an inventory. An unrecognised value also means "dry_run",
    so that a typo never enforces.
    """
    name = "CLOUD_RESEARCH_ENVIRONMENTS_EXPIRED_ACCESS_ENFORCEMENT"
    value = getattr(settings, name, EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN)
    mode = str(value).strip().lower().replace("-", "_")
    if mode not in _EXPIRED_ACCESS_ENFORCEMENT_MODES:
        logger.error(
            "Unrecognised %s value %r; using %r",
            name,
            value,
            EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN,
        )
        return EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN
    return mode
