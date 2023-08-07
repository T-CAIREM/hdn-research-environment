from datetime import timedelta
from typing import Iterable

from background_task import background
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from environment.mailers import send_environment_access_expired
from environment.models import BillingAccountSharingInvite
from environment.services import (
    delete_environment,
    get_environment_project_pairs_with_expired_access,
    share_billing_account,
    stop_running_environment,
)

User = get_user_model()

Event = apps.get_model("events", "Event")


def _expired_environment_termination_schedule():
    return timezone.now() + timedelta(days=14)


@background
@transaction.atomic
def give_user_permission_to_access_billing_account(
    invite_id: int, owner_email: str, user_email: str, billing_account_id: str
):
    invite = BillingAccountSharingInvite.objects.get(pk=invite_id)
    invite.is_consumed = True
    invite.save()
    share_billing_account(owner_email, user_email, billing_account_id)


@background
def stop_event_participants_environments_with_expired_access(event_id: int):
    event = Event.objects.prefetch_related("participants").get(pk=event_id)
    for participant in event.participants.all():
        stop_environments_with_expired_access(participant.user_id)


@background
def stop_environments_with_expired_access(user_id: int):
    user = User.objects.select_related("cloud_identity").get(pk=user_id)

    expired_pairs = get_environment_project_pairs_with_expired_access(user)
    environments, projects = zip(*expired_pairs)
    for environment in environments:
        if environment.is_running:
            stop_running_environment(
                workbench_type=environment.type,
                workbench_resource_id=environment.instance_name,
                user_email=user.cloud_identity.email,
                workspace_project_id=environment.workspace_name,
            )
    send_environment_access_expired(user, projects)
    if len(environments) > 0:
        environment_ids = [environment.id for environment in environments]
        terminate_environments_if_access_still_expired(
            user_id,
            environment_ids,
            schedule=_expired_environment_termination_schedule(),
        )


@background
def terminate_environments_if_access_still_expired(
    user_id: int, previously_stopped_environment_ids: Iterable[str]
):
    user = User.objects.get(pk=user_id)
    expired_pairs = get_environment_project_pairs_with_expired_access(user)
    for environment, project in expired_pairs:
        if environment.id in previously_stopped_environment_ids:
            delete_environment(
                user_email=user.cloud_identity.email,
                dataset_identifier=environment.dataset_identifier,
                workspace_project_id=environment.workspace_name,
                region=environment.region.value,
                bucket_name=project.project_file_root(),
                machine_type=environment.machine_type,
                workbench_type=environment.type.value,
                disk_size=environment.disk_size,
                gpu_accelerator_type=environment.gpu_accelerator_type,
                workbench_resource_id=environment.gcp_identifier,
            )
