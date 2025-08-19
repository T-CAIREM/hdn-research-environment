from typing import Callable, Iterator, Optional, Tuple, TypeVar

from django.db.models import Model
from environment.entities import ServiceError

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")

User = Model


def user_has_cloud_identity(user: User) -> bool:
    return hasattr(user, "cloud_identity")


def user_has_access_billing_account(billing_accounts_list) -> bool:
    return bool(billing_accounts_list)


def user_workspace_setup_done(user: User) -> bool:
    if not user_has_cloud_identity(user):
        return False
    return user.cloud_identity.initial_workspace_setup_done


def inner_join_iterators(
    key_left: Callable[[T], V],
    left: Iterator[T],
    key_right: Callable[[U], V],
    right: Iterator[U],
) -> Iterator[Tuple[T, U]]:
    right_dict = {key_right(element): element for element in right}
    return [
        (element, right_dict[key_left(element)])
        for element in left
        if key_left(element) in right_dict
    ]


def left_join_iterators(
    key_left: Callable[[T], V],
    left: Iterator[T],
    key_right: Callable[[U], V],
    right: Iterator[U],
) -> Iterator[Tuple[T, Optional[U]]]:
    right_dict = {key_right(element): element for element in right}
    return [(element, right_dict.get(key_left(element))) for element in left]


def has_service_errors(workspace_or_workbench) -> bool:
    """Check if workspace or workbench has service errors."""
    return (
        workspace_or_workbench.service_errors is not None
        and len(workspace_or_workbench.service_errors) > 0
    )


def has_error_type(workspace_or_workbench, error_type: str) -> bool:
    """Generic function to check if workspace or workbench has a specific error type."""
    if not has_service_errors(workspace_or_workbench):
        return False
    return any(error.error_type == error_type for error in workspace_or_workbench.service_errors)


def has_billing_error(workspace_or_workbench) -> bool:
    """Check if workspace or workbench has billing-related errors."""
    return has_error_type(workspace_or_workbench, "billing_disabled")


def has_api_error(workspace_or_workbench) -> bool:
    """Check if workspace or workbench has API-related errors."""
    return has_error_type(workspace_or_workbench, "api_not_enabled")


def has_permission_error(workspace_or_workbench) -> bool:
    """Check if workspace or workbench has permission-related errors."""
    return has_error_type(workspace_or_workbench, "permission_denied")


def get_errors_by_type(workspace_or_workbench, error_type: str) -> list:
    """Get all errors of a specific type."""
    if not has_service_errors(workspace_or_workbench):
        return []
    return [error for error in workspace_or_workbench.service_errors if error.error_type == error_type]


def get_critical_errors(workspace_or_workbench) -> list:
    """Get all critical errors that would make the entity non-functional."""
    critical_error_types = ["permission_denied", "not_found", "billing_disabled"]
    if not has_service_errors(workspace_or_workbench):
        return []
    return [error for error in workspace_or_workbench.service_errors 
            if error.error_type in critical_error_types]


def has_billing_issues(workspace) -> bool:
    """
    Comprehensive billing validation for workspaces.
    Returns True if the workspace has any billing problems that should zone it out.
    """
    # Check service errors first
    if has_billing_error(workspace):
        return True
    
    # Additional validation: Check if billing account is properly configured
    if not workspace.gcp_billing_id:
        return True  # No billing account attached
    
    # Check workspace accessibility (covers billing account access issues)
    if hasattr(workspace, 'is_accessible') and not workspace.is_accessible:
        # Check if the access denial is billing-related
        if hasattr(workspace, 'access_denial_reason') and workspace.access_denial_reason:
            billing_keywords = ["billing", "account", "closed", "inactive", "revoked"]
            if any(keyword in workspace.access_denial_reason.lower() for keyword in billing_keywords):
                return True
    
    return False


def requires_billing_change(workspace) -> bool:
    """
    Check if workspace requires billing account change to become functional.
    This determines if we should show the 'Change Billing' button.
    """
    return has_billing_issues(workspace)


def get_billing_link(workspace_id: str) -> str:
    """Generate billing enable link for a workspace."""
    return f"https://console.developers.google.com/billing/enable?project={workspace_id}"


def format_error_message(error: ServiceError) -> str:
    """Format error message for display in templates."""
    error_formats = {
        "billing_disabled": lambda e: f"⚠️ Billing disabled: {e.message}",
        "api_not_enabled": lambda e: f"⏳ APIs enabling: {e.service_name} APIs are being enabled",
        "permission_denied": lambda e: f"🚫 Access denied: {e.message}",
        "quota_exceeded": lambda e: f"📊 Quota exceeded: {e.message}",
        "not_found": lambda e: f"❓ Resource not found: {e.message}",
        "unknown": lambda e: f"❌ Error: {e.message}",
    }
    
    formatter = error_formats.get(error.error_type, error_formats["unknown"])
    return formatter(error)


def get_error_action_text(error: ServiceError) -> Optional[str]:
    """Get action text for error types that have user actions."""
    action_text_map = {
        "billing_disabled": "Enable billing",
        "quota_exceeded": "Retry later" if hasattr(error, 'can_retry') and error.can_retry else None,
    }
    return action_text_map.get(error.error_type)


def get_error_action_link(error: ServiceError) -> Optional[str]:
    """Get action link for error types that have user actions."""
    if error.error_type == "billing_disabled":
        return get_billing_link(error.resource_id)
    return None


def get_error_css_class(error: ServiceError) -> str:
    """Get CSS class for error type."""
    error_type_map = {
        "billing_disabled": "error-billing",
        "api_not_enabled": "error-api",
        "permission_denied": "error-permission",
        "quota_exceeded": "error-quota",
        "not_found": "error-permission",
        "unknown": "error-unknown",
    }
    return error_type_map.get(error.error_type, "error-unknown")


def get_error_severity(error: ServiceError) -> str:
    """Get error severity level."""
    severity_map = {
        "billing_disabled": "critical",
        "permission_denied": "critical", 
        "not_found": "critical",
        "api_not_enabled": "warning",
        "quota_exceeded": "warning",
        "unknown": "info",
    }
    return severity_map.get(error.error_type, "info")


def group_errors_by_severity(errors: list) -> dict:
    """Group errors by severity level."""
    grouped = {"critical": [], "warning": [], "info": []}
    for error in errors:
        severity = get_error_severity(error)
        grouped[severity].append(error)
    return grouped


def workspace_is_functional(workspace) -> bool:
    """
    Check if workspace is functional (no critical errors AND billing is properly configured).
    This determines if workspace features should be available to users.
    """
    # First check billing - this is now the primary gate
    if has_billing_issues(workspace):
        return False
    
    # Then check service errors for other critical issues
    if not has_service_errors(workspace):
        return True
    
    # Consider workspace non-functional if it has other critical errors
    critical_errors = ["permission_denied", "not_found", "api_not_enabled"]
    return not any(error.error_type in critical_errors for error in workspace.service_errors)


def workbench_is_accessible(workbench) -> bool:
    """Check if workbench is accessible (no service errors)."""
    return not has_service_errors(workbench)
