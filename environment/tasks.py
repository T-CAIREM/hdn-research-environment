from typing import Iterable
from datetime import timedelta

from background_task import background
from django.contrib.auth import get_user_model
from django.apps import apps
from django.utils import timezone

from environment.utilities import user_has_billing_setup
from environment.services import (
    get_environment_project_pairs_with_expired_access,
    stop_running_environment,
    delete_environment,
    send_environment_access_expired_email,
)


User = get_user_model()

Event = apps.get_model("events", "Event")


def _expired_environment_termination_schedule():
    return timezone.now() + timedelta(days=14)


@background
def stop_event_participants_environments_with_expired_access(event_id: int):
    event = Event.objects.prefetch_related("participants").get(pk=event_id)
    for participant in event.participants.all():
        stop_environments_with_expired_access(participant.user_id)


@background
def stop_environments_with_expired_access(user_id: int):
    user = User.objects.select_related("cloud_identity__billing_setup").get(pk=user_id)

    if not user_has_billing_setup(user):
        return

    expired_pairs = get_environment_project_pairs_with_expired_access(user)
    environments, projects = zip(*expired_pairs)
    for environment in environments:
        if environment.is_running:
            stop_running_environment(user, environment.id, environment.region)
    send_environment_access_expired_email(user, projects)
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
    for environment, _ in expired_pairs:
        if environment.id in previously_stopped_environment_ids:
            delete_environment(user, environment.id, environment.region)
