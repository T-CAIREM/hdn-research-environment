import json
import logging
from datetime import timedelta
from typing import Any, Iterable, Optional

from background_task import background
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from environment.config import (
    EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN,
    EXPIRED_ACCESS_ENFORCEMENT_OFF,
    get_expired_access_enforcement,
)
from environment.entities import ResearchEnvironment
from environment.mailers import send_environment_access_expired
from environment.models import BillingAccountSharingInvite
from environment.services import (
    delete_environment,
    get_environment_project_pairs_with_expired_access,
    share_billing_account,
    stop_running_environment,
)
from environment.utilities import user_has_cloud_identity

logger = logging.getLogger(__name__)

User = get_user_model()

Event = apps.get_model("events", "Event")


def _expired_environment_termination_schedule():
    return timezone.now() + timedelta(days=14)


def _load_enforcement_user(task: str, user_id: int, mode: str):
    """The user to enforce expired access for, or None when there is nothing to do."""
    if mode == EXPIRED_ACCESS_ENFORCEMENT_OFF:
        logger.debug("%s skipped for user_id=%s: enforcement is off", task, user_id)
        return None
    user = User.objects.select_related("cloud_identity").get(pk=user_id)
    if not user_has_cloud_identity(user):
        # Workbenches are only ever created through a cloud identity.
        logger.info("%s skipped for user_id=%s: no cloud identity", task, user_id)
        return None
    return user


def _log_dry_run(
    task: str,
    action: str,
    user_id: int,
    environment: ResearchEnvironment,
    project: Optional[Any],
) -> None:
    """One INFO line per workbench that an enforcing run would act on."""
    details = {
        "task": task,
        "action": action,
        "user_id": user_id,
        "workbench": environment.gcp_identifier,
        "workbench_type": environment.type.value,
        "workbench_status": environment.status.value,
        "workspace": environment.workspace_name,
        "dataset": environment.dataset_identifier,
        "project": (
            None if project is None else f"{project._meta.model_name}:{project.pk}"
        ),
    }
    logger.info(
        "Expired-access dry run: %s",
        json.dumps(details, sort_keys=True),
        extra={"expired_access_dry_run": details},
    )


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
    """Stop workbenches whose data access expired, mail the user, and queue
    their termination 14 days later.

    In dry_run mode each affected workbench is logged instead, with action
    "stop" when it is running and "already_stopped" otherwise; an enforcing
    run would also mail the user and queue termination for every logged
    workbench. Nothing is stopped, mailed or queued.
    """
    task = "stop_environments_with_expired_access"
    mode = get_expired_access_enforcement()
    user = _load_enforcement_user(task, user_id, mode)
    if user is None:
        return

    expired_pairs = get_environment_project_pairs_with_expired_access(user)
    if not expired_pairs:
        return
    if mode == EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN:
        for environment, project in expired_pairs:
            action = "stop" if environment.is_running else "already_stopped"
            _log_dry_run(task, action, user_id, environment, project)
        return

    environments, projects = zip(*expired_pairs)
    for environment in environments:
        if environment.is_running:
            stop_running_environment(
                workbench_type=environment.type.value,
                workbench_resource_id=environment.gcp_identifier,
                user=user,
                workspace_project_id=environment.workspace_name,
            )
    # `projects` may contain None for a draft that no longer exists (deleted, or
    # published); the template renders a generic line for those.
    send_environment_access_expired(user, projects)
    environment_ids = [environment.gcp_identifier for environment in environments]
    terminate_environments_if_access_still_expired(
        user_id,
        environment_ids,
        schedule=_expired_environment_termination_schedule(),
    )


@background
def terminate_environments_if_access_still_expired(
    user_id: int, previously_stopped_environment_ids: Iterable[str]
):
    task = "terminate_environments_if_access_still_expired"
    mode = get_expired_access_enforcement()
    user = _load_enforcement_user(task, user_id, mode)
    if user is None:
        return

    expired_pairs = get_environment_project_pairs_with_expired_access(user)
    for environment, project in expired_pairs:
        if environment.gcp_identifier in previously_stopped_environment_ids:
            if mode == EXPIRED_ACCESS_ENFORCEMENT_DRY_RUN:
                _log_dry_run(task, "delete", user_id, environment, project)
                continue
            delete_environment(
                user=user,
                workspace_project_id=environment.workspace_name,
                workbench_type=environment.type.value,
                workbench_resource_id=environment.gcp_identifier,
            )
