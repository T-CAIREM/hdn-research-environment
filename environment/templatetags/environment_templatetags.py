from django.template.defaulttags import register
from environment.utilities import (
    has_service_errors,
    has_billing_error,
    requires_billing_change,
    has_api_error,
    has_permission_error,
    get_billing_link,
    format_error_message,
    get_error_action_text,
    get_error_action_link,
    get_error_css_class,
    workspace_is_functional,
    workbench_is_accessible,
)


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
