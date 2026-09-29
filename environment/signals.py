from datetime import datetime
from typing import Iterable
import logging

from background_task.tasks import TaskSchedule
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_init, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

from environment.config import draft_workbenches_enabled
from environment.models import BillingAccountSharingInvite, CloudIdentity
from environment.tasks import (
    give_user_permission_to_access_billing_account,
    stop_environments_with_expired_access,
    stop_event_participants_environments_with_expired_access,
)
from environment.utilities import user_has_cloud_identity

# Setting up constants for Cache
CACHE_TIMEOUT = 60 * 60 * 24 * 15  # 15 days
CACHE_KEY_PREFIX = "pending_billing_share_"

logger = logging.getLogger(__name__)

User = get_user_model()

Training = apps.get_model("user", "Training")

DataAccessRequest = apps.get_model("project", "DataAccessRequest")

Event = apps.get_model("events", "Event")

EventApplication = apps.get_model("events", "EventApplication")

ActiveProject = apps.get_model("project", "ActiveProject")


@receiver(post_save, sender=BillingAccountSharingInvite)
@receiver(post_save, sender=CloudIdentity)
def consume_billing_account_sharing_invites(sender, created, instance, **kwargs):
    if sender is CloudIdentity:
        if not created:
            return
        cloud_identity = instance
        outstanding_invites = (
            cloud_identity.user.user_billingaccountsharinginvite_set.select_related(
                "owner__cloud_identity"
            ).filter(is_consumed=False)
        )
    else:  # BillingAccountSharingInvite
        if (
            not hasattr(instance.user, "cloud_identity")
            or instance.is_revoked
            or instance.is_consumed
        ):
            # The user that used the invite does not have a CloudIdentity yet.
            # The invite record will be consumed after the CloudIdentity is created.
            # See the `sender is CloudIdentity` case.
            # Or the invite was revoked/consumed, triggering the signal.
            return
        outstanding_invites = [instance]
        cloud_identity = instance.user.cloud_identity

    for invite in outstanding_invites:
        _queue_billing_account_share(invite, cloud_identity.email)


def _queue_billing_account_share(invite: BillingAccountSharingInvite, user_email: str):
    """Queue the retried share task once the invite (and whatever saved it) commits.

    The task reads the invite back by id, so it must never run first. An
    identical task that is still pending is not queued twice.
    """
    owner_email = invite.owner.cloud_identity.email
    transaction.on_commit(
        lambda: give_user_permission_to_access_billing_account(
            invite.id,
            owner_email,
            user_email,
            invite.billing_account_id,
            schedule=TaskSchedule(action=TaskSchedule.CHECK_EXISTING),
        )
    )


@receiver(post_init, sender=User)
def memoize_original_credentialing_status(instance: User, **kwargs):
    # Instances loaded with deferred fields (.only()/.defer() querysets, in
    # particular the deletion collector's cascade fetch during a cascade
    # delete) must not be memoized: reading a deferred field runs a refresh
    # query that instantiates another instance of this model, re-firing this
    # receiver in an infinite recursion. Such instances are never saved by
    # the environment workflows, so skipping them is safe; the post_save
    # receivers fall back to a no-op default when the memo is absent.
    if instance.get_deferred_fields():
        return
    instance._original_is_credentialed = instance.is_credentialed


@receiver(post_save, sender=User)
def schedule_stop_environments_if_credentialing_revoked(instance: User, **kwargs):
    if not instance.is_credentialed and getattr(
        instance, "_original_is_credentialed", False
    ):
        stop_environments_with_expired_access(instance.id)


@receiver(post_init, sender=Event)
def memoize_original_event_end_time(instance: Event, **kwargs):
    if instance.get_deferred_fields():  # see memoize_original_credentialing_status
        return
    instance._original_end_date = instance.end_date


@receiver(post_save, sender=Event)
def schedule_stop_environments_if_event_finished(
    instance: Event, created: bool, **kwargs
):
    original_end_date = getattr(instance, "_original_end_date", instance.end_date)
    if original_end_date != instance.end_date or created:
        schedule = datetime.combine(instance.end_date, datetime.min.time())
        stop_event_participants_environments_with_expired_access(
            instance.id, schedule=schedule
        )


@receiver(post_init, sender=Training)
def memoize_original_validity(instance: Training, **kwargs):
    if instance.get_deferred_fields():  # see memoize_original_credentialing_status
        return
    instance._original_is_valid = instance.is_valid()


@receiver(post_save, sender=Training)
def schedule_stop_environment_if_training_accepted(instance: Training, **kwargs):
    user = instance.user

    if instance.is_valid() and not getattr(instance, "_original_is_valid", False):
        schedule = instance.process_datetime + instance.training_type.valid_duration
        stop_environments_with_expired_access(user.id, schedule=schedule)


@receiver(post_init, sender=DataAccessRequest)
def memoize_original_acceptation_status(instance: DataAccessRequest, **kwargs):
    if instance.get_deferred_fields():  # see memoize_original_credentialing_status
        return
    instance._original_is_accepted = instance.is_accepted()
    instance._original_is_revoked = instance.is_revoked()


@receiver(post_save, sender=DataAccessRequest)
def schedule_stop_environment_if_data_access_request_accepted_or_revoked(
    instance: DataAccessRequest, **kwargs
):
    user = instance.requester

    request_was_accepted = instance.is_accepted() and not getattr(
        instance, "_original_is_accepted", False
    )
    access_was_revoked = instance.is_revoked() and not getattr(
        instance, "_original_is_revoked", False
    )
    if request_was_accepted:
        if request_was_accepted and not instance.duration:  # Indefinite access
            return
        schedule = timezone.now() + instance.duration
        stop_environments_with_expired_access(user.id, schedule=schedule)
    elif access_was_revoked:
        stop_environments_with_expired_access(user.id)


def _submitting_author_user_ids(active_project) -> Iterable[int]:
    return list(
        active_project.authors.filter(
            is_submitting=True, user__isnull=False
        ).values_list("user_id", flat=True)
    )


@receiver(post_save, sender=ActiveProject)
def schedule_stop_environments_if_draft_no_longer_editable(instance, **kwargs):
    # A draft-backed workbench mounts the draft's prefix read-write, and the
    # mount mode cannot be changed on a live workbench. Once the authors can no
    # longer edit the draft (submitted, archived), its workbenches are stopped
    # by the same reaper that handles revoked dataset access.
    if not draft_workbenches_enabled() or instance.author_editable():
        return
    for user_id in _submitting_author_user_ids(instance):
        stop_environments_with_expired_access(user_id)


@receiver(pre_delete, sender=ActiveProject)
def schedule_stop_environments_when_draft_removed(instance, **kwargs):
    # Publication deletes the ActiveProject row inside a transaction and its
    # Author rows cascade with it, so the submitting authors must be collected
    # before the delete runs.
    if not draft_workbenches_enabled():
        return
    for user_id in _submitting_author_user_ids(instance):
        stop_environments_with_expired_access(user_id)


@receiver(post_init, sender=EventApplication)
def memoize_original_application_status(instance, **kwargs):
    """Store the original status to detect changes"""
    if instance.get_deferred_fields():  # see memoize_original_credentialing_status
        return
    instance._original_status = getattr(instance, "status", None)


@receiver(post_save, sender=EventApplication)
def handle_event_billing_account_on_approval(instance, **kwargs):
    """Share the event's billing account with a newly approved participant.

    The share always goes through a BillingAccountSharingInvite owned by the
    event host, so it is durable and retried. For a user who already has a
    cloud identity, the invite's post_save queues the share task once the
    approval commits. Otherwise the share is queued when the identity is
    created. An existing invite for the same user and billing account is
    reused, and its share queued again, instead of creating a duplicate.
    """
    if not (
        instance.status == instance.EventApplicationStatus.APPROVED
        and getattr(instance, "_original_status", None)
        != instance.EventApplicationStatus.APPROVED
        and instance.event.gcp_billing_id
    ):
        return

    event = instance.event
    user = instance.user
    billing_account_id = event.gcp_billing_id

    if not user_has_cloud_identity(event.host):
        # The share is made on the owner's behalf; without the host's identity
        # there is no one to share from.
        logger.error(
            "Event %s has billing account %s but its host has no cloud identity; "
            "not sharing it with user %s",
            event.pk,
            billing_account_id,
            user.pk,
        )
        return

    invite = (
        BillingAccountSharingInvite.objects.filter(
            user=user, billing_account_id=billing_account_id, is_revoked=False
        )
        .select_related("owner__cloud_identity")
        .order_by("pk")
        .first()
    )
    if invite is None:
        # Its post_save (consume_billing_account_sharing_invites) queues the
        # share if the user already has a cloud identity.
        invite = BillingAccountSharingInvite.objects.create(
            owner=event.host,
            user=user,
            user_contact_email=user.email,
            billing_account_id=billing_account_id,
        )
        logger.info(
            "Queued billing account %s share for user %s through invite %s (event %s)",
            billing_account_id,
            user.pk,
            invite.pk,
            event.pk,
        )
    elif user_has_cloud_identity(user):
        # Sharing is idempotent; queue it again in case the earlier task was
        # lost or the grant was undone.
        _queue_billing_account_share(invite, user.cloud_identity.email)
        logger.info(
            "Re-queued billing account %s share for user %s through existing "
            "invite %s (event %s)",
            billing_account_id,
            user.pk,
            invite.pk,
            event.pk,
        )
