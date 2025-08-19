from django.template.defaulttags import register
from environment.utilities import (
    has_service_errors,
    requires_billing_change,
    has_api_error,
    has_permission_error,
    get_billing_link,
    format_error_message,
    get_error_action_text,
    get_error_action_link,
    get_error_css_class,
    get_error_severity,
    get_errors_by_type,
    get_critical_errors,
    workspace_is_functional,
    workbench_is_accessible,
)


@register.inclusion_tag("tag/service_error_display.html")
def service_error_display(entity, error_prefix=None, group_by_severity=False):
    """
    Display service errors for any entity (workspace, workbench, etc.)
    
    Args:
        entity: The entity with potential service_errors attribute
        error_prefix: Optional prefix text for error messages (e.g., "Workbench Error")
        group_by_severity: Whether to group errors by severity level
    """
    return {
        "entity": entity,
        "error_prefix": error_prefix,
        "group_by_severity": group_by_severity,
    }


@register.filter
def get_dict_value(dictionary, key):
    return dictionary.get(key)


@register.filter
def has_errors(workspace):
    """Check if workspace has service errors."""
    return has_service_errors(workspace)


@register.filter
def has_billing_issues(workspace):
    """Check if workspace has comprehensive billing issues."""
    from environment.utilities import has_billing_issues as billing_check
    return billing_check(workspace)


@register.filter
def needs_billing_change(workspace):
    """Check if workspace requires billing account change."""
    return requires_billing_change(workspace)


@register.filter
def has_api_issues(workspace):
    """Check if workspace has API-related errors."""
    return has_api_error(workspace)


@register.filter
def has_permission_issues(workspace):
    """Check if workspace has permission-related errors."""
    return has_permission_error(workspace)


@register.filter  
def billing_link(workspace_id):
    """Generate billing enable link for a workspace."""
    return get_billing_link(workspace_id)


@register.filter
def error_message(error):
    """Format error message for display."""
    return format_error_message(error)


@register.filter
def error_action_text(error):
    """Get action text for error."""
    return get_error_action_text(error)


@register.filter
def error_action_link(error):
    """Get action link for error."""
    return get_error_action_link(error)


@register.filter
def error_css_class(error):
    """Get CSS class for error type."""
    return get_error_css_class(error)


@register.filter
def workspace_functional(workspace):
    """Check if workspace is functional."""
    return workspace_is_functional(workspace)


@register.filter
def workbench_accessible(workbench):
    """Check if workbench is accessible."""
    return workbench_is_accessible(workbench)


@register.filter
def error_severity(error):
    """Get error severity level."""
    return get_error_severity(error)


@register.filter
def errors_by_type(entity, error_type):
    """Get errors of a specific type."""
    return get_errors_by_type(entity, error_type)


@register.filter
def critical_errors(entity):
    """Get critical errors only."""
    return get_critical_errors(entity)


@register.filter
def group_errors(errors):
    """Group errors by severity."""
    from environment.utilities import group_errors_by_severity
    return group_errors_by_severity(errors)
