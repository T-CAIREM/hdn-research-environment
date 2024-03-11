from django.urls import path

from environment import views

urlpatterns = [
    path("", views.research_environments, name="research_environments"),
    path(
        "billing/manage/<billing_account_id>",
        views.manage_billing_account,
        name="manage_billing_account",
    ),
    path(
        "billing/confirm",
        views.confirm_billing_account_sharing,
        name="confirm_billing_account_sharing",
    ),
    path(
        "environments-card/",
        views.research_environments_partial,
        name="research_environments_partial",
    ),
    path(
        "identity-provisioning/",
        views.identity_provisioning,
        name="identity_provisioning",
    ),
    path(
        "environment/stop",
        views.stop_running_environment,
        name="stop_running_environment",
    ),
    path(
        "environment/start",
        views.start_stopped_environment,
        name="start_stopped_environment",
    ),
    path(
        "environment/update",
        views.change_environment_machine_type,
        name="change_environment_machine_type",
    ),
    path("environment/delete", views.delete_environment, name="delete_environment"),
    path(
        "environment/create/<workspace_id>",
        views.create_research_environment,
        name="create_research_environment",
    ),
    path(
        "execution/check-status",
        views.check_execution_status,
        name="check_execution_status",
    ),
    path("workspace/create", views.create_workspace, name="create_workspace"),
    path("workspace/delete", views.delete_workspace, name="delete_workspace"),
    path(
        "sharing/workspace/create",
        views.create_shared_workspace,
        name="create_shared_workspace",
    ),
    path(
        "sharing/workspace/delete",
        views.delete_shared_workspace,
        name="delete_shared_workspace",
    ),
    path(
        "sharing/bucket/create/<workspace_id>",
        views.create_shared_bucket,
        name="create_shared_bucket",
    ),
    path(
        "sharing/bucket/delete", views.delete_shared_bucket, name="delete_shared_bucket"
    ),
    path(
        "sharing/manage/<shared_workspace_name>/<shared_bucket_name>",
        views.manage_shared_bucket,
        name="manage_shared_bucket",
    ),
    path(
        "sharing/manage/<shared_workspace_name>/<shared_bucket_name>/files",
        views.manage_shared_bucket_files,
        name="manage_shared_bucket_files",
    ),
    path(
        "sharing/confirm",
        views.confirm_bucket_sharing,
        name="confirm_bucket_sharing",
    ),
    path(
        "sharing/generate_signed_url/<bucket_name>",
        views.generate_signed_url,
        name="generate_bucket_signed_url",
    ),
    path(
        "sharing/<bucket_name>",
        views.get_shared_bucket_content,
        name="get_shared_bucket_content",
    ),
    path(
        "sharing/<bucket_name>/content/create",
        views.create_shared_bucket_directory,
        name="create_shared_bucket_directory",
    ),
    path(
        "sharing/<bucket_name>/content/delete",
        views.delete_shared_bucket_content,
        name="delete_shared_bucket_content",
    ),
]
