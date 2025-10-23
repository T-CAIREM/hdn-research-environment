import json
import datetime
from typing import Iterable, Tuple

from django import template
from django.apps import apps
from django.urls import reverse
from django.utils import timezone

from environment.entities import (
    ResearchEnvironment,
    ResearchWorkspace,
    SharedWorkspace,
    SharedBucket,
)

from environment.models import VMInstance
from environment.utilities import has_billing_issues

PublishedProject = apps.get_model("project", "PublishedProject")


register = template.Library()


button_types = {
    "pause": {
        "button_text": "Pause",
        "http_method": "PATCH",
        "url_name": "stop_running_environment",
        "button_class": "btn btn-outline-secondary m-1",
    },
    "start": {
        "button_text": "Start",
        "http_method": "PATCH",
        "url_name": "start_stopped_environment",
        "button_class": "btn btn-primary m-1",
    },
    "update": {
        "button_text": "Save Instance",
        "http_method": "PATCH",
        "url_name": "change_environment_machine_type",
        "button_class": "btn btn-primary m-1",
    },
    "destroy": {
        "button_text": "Destroy",
        "http_method": "DELETE",
        "url_name": "delete_environment",
        "button_class": "btn btn-danger m-1",
    },
    "leave": {
        "button_text": "Leave",
        "http_method": "POST",
        "url_name": "leave_shared_environment",
        "button_class": "btn btn-danger m-1",
    },
    "renew": {
        "button_text": "Renew Certificate",
        "http_method": "PATCH",
        "url_name": "renew_environment_certificate",
        "button_class": "btn btn-primary m-1",
    },
    "modal_instance": {
        "button_text": "Change Instance Type",
        "button_class": "btn btn-primary m-1",
        "modal_title": "Choose Instance Type",
        "modal_body": None,
        "action_button_type": "update",
    },
    "modal_pause": {
        "button_text": "Pause",
        "button_class": "btn btn-outline-secondary",
        "modal_title": "Pause",
        "modal_body": "Are you sure you want to pause this environment?",
        "action_button_type": "pause",
    },
    "modal_destroy": {
        "button_text": "Destroy",
        "button_class": "btn btn-danger",
        "modal_title": "Destroy",
        "modal_body": "Are you sure you want to destroy this environment?",
        "action_button_type": "destroy",
    },
    "modal_start": {
        "button_text": "Start",
        "button_class": "btn btn-secondary m1",
        "modal_title": "Start",
        "modal_body": "Are you sure you want to start this environment?",
        "action_button_type": "start",
    },
    "modal_leave": {
        "button_text": "Leave",
        "button_class": "btn btn-danger",
        "modal_title": "Leave Environment",
        "modal_body": "Are you sure you want to leave this shared environment? You will lose access to it.",
        "action_button_type": "leave",
    },
    "modal_renew": {
        "button_text": "Renew Certificate",
        "button_class": "btn-warning",
        "modal_title": "Renew Certificate",
        "modal_body": "",
        "action_button_type": "renew",
    },
}


@register.inclusion_tag("tag/environment_modal_button.html")
def environment_modal_button(
    environment: ResearchEnvironment,
    button_type: str,
) -> dict:
    data = button_types[button_type]
    result_data = {
        "environment": environment,
        "project": environment.project,
        "button_text": data["button_text"],
        "button_class": data["button_class"],
        "modal_title": data["modal_title"],
        "modal_body": data["modal_body"],
        "modal_id": f"{data['action_button_type']}-{environment.gcp_identifier}",
        "action_button_type": data["action_button_type"],
    }
    if button_type == "modal_instance":
        MACHINE_TYPE_SPECIFICATION = {}
        for instance in VMInstance.objects.filter(
            region__region=environment.region.value
        ):
            MACHINE_TYPE_SPECIFICATION[instance.get_instance_value()] = instance
        result_data["instances_dict"] = MACHINE_TYPE_SPECIFICATION

    return result_data


@register.inclusion_tag("tag/environment_action_button.html")
def environment_action_button(
    environment: ResearchEnvironment,
    button_type: str,
) -> dict:
    data = button_types[button_type]
    request_data = {
        "gcp_project_id": environment.workspace_name,
        "instance_name": environment.gcp_identifier,
        "environment_type": environment.type.value,
    }

    if button_type == "leave":
        request_data["service_account_name"] = environment.service_account_name

    result_data = {
        "button_class": data["button_class"],
        "button_text": data["button_text"],
        "button_type": button_type,
        "url": reverse(data["url_name"]),
        "http_method": data["http_method"],
        "request_data": json.dumps(request_data),
    }
    return result_data


@register.inclusion_tag("tag/environment_renew_certificate_modal.html")
def environment_renew_certificate_modal(
    environment: ResearchEnvironment,
    button_type: str,
) -> dict:
    data = button_types[button_type]
    expiration_date_str = getattr(
        environment, "rstudio_ssl_certificate_expiration_date", None
    )
    is_expired = False
    show_renew_button = False

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry_date = datetime.datetime.strptime(
            expiration_date_str, "%Y-%m-%dT%H:%M:%SZ"
        )
        expiry_date = expiry_date.replace(tzinfo=datetime.timezone.utc)
        expiry_date_formatted = expiry_date.strftime("%Y-%m-%d")
        is_expired = now > expiry_date
        show_renew_button = (expiry_date - now).days <= 14
    except Exception:
        expiry_date_formatted = expiration_date_str
    button_class = "btn-danger" if is_expired else "btn-warning"
    modal_body = (
        f"Your SSL certificate expired on <strong>{expiry_date_formatted}</strong>. "
        "Please renew it to restore HTTPS security and access to your environment."
        if is_expired
        else f"Your SSL certificate will expire on <strong>{expiry_date_formatted}</strong>. "
        "If you do not renew it, your environment will lose HTTPS security and may become inaccessible."
    )

    result_data = {
        "environment": environment,
        "show_renew_button": show_renew_button,
        "modal_body": modal_body,
        "modal_title": data["modal_title"],
        "modal_id": f"{data['action_button_type']}-{environment.gcp_identifier}",
        "button_class": button_class,
        "button_text": data["button_text"],
        "action_button_type": data["action_button_type"],
    }
    return result_data


@register.inclusion_tag("tag/bucket_modal_button.html")
def delete_shared_bucket_modal_button(
    shared_bucket: SharedBucket,
) -> dict:
    request_data = {"bucket_name": shared_bucket.name}

    result_data = {
        "button_text": "Destroy",
        "modal_title": "Destroy",
        "modal_body": "Are you sure you want to destroy this bucket?",
        "button_class": "btn-danger",
        "modal_id": f"workspace-delete-{shared_bucket.name}",
        "button_type": "shared_bucket_delete",
        "request_url": reverse("delete_shared_bucket"),
        "request_method": "DELETE",
        "request_data": json.dumps(request_data),
    }
    return result_data


@register.inclusion_tag("tag/workspace_destroy_modal_button.html")
def workspace_destroy_modal_button(
    workspace: ResearchWorkspace,
) -> dict:
    request_data = {
        "gcp_project_id": workspace.gcp_project_id,
        "billing_account_id": workspace.gcp_billing_id,
    }
    result_data = {
        "workspace": workspace,
        "modal_id": f"workspace-delete-{workspace.gcp_project_id}",
        "button_type": "workspace_delete",
        "request_url": reverse("delete_workspace"),
        "request_method": "DELETE",
        "request_data": json.dumps(request_data),
        "disabled": len(workspace.workbenches) > 0,
    }
    return result_data


@register.inclusion_tag("tag/workspace_destroy_modal_button.html")
def shared_workspace_destroy_modal_button(
    shared_workspace: SharedWorkspace,
) -> dict:
    request_data = {
        "gcp_project_id": shared_workspace.gcp_project_id,
        "billing_account_id": shared_workspace.gcp_billing_id,
    }
    has_billing_issues_flag = has_billing_issues(shared_workspace)
    result_data = {
        "shared_workspace": shared_workspace,
        "modal_id": f"shared-workspace-delete-{shared_workspace.gcp_project_id}",
        "button_type": "shared_workspace_delete",
        "request_url": reverse("delete_shared_workspace"),
        "request_method": "DELETE",
        "request_data": json.dumps(request_data),
        "disabled": len(shared_workspace.buckets) > 0 or has_billing_issues_flag,
        "has_billing_issues": has_billing_issues_flag,
    }
    return result_data


@register.inclusion_tag("tag/group_modal_button.html")
def delete_group_modal_button(
    cloud_group_name: str,
) -> dict:
    result_data = {
        "button_text": "Delete Group",
        "modal_title": "Delete Group",
        "modal_body": "Are you sure you want to delete this group?",
        "button_class": "btn-danger",
        "modal_id": f"group-delete-{cloud_group_name}",
        "button_type": "cloud_group_delete",
        "cloud_group_name": cloud_group_name,
    }
    return result_data
