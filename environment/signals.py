from datetime import datetime
from typing import Iterable
import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.cache import cache

from environment.models import BillingAccountSharingInvite, CloudIdentity
from environment.tasks import (
    give_user_permission_to_access_billing_account,
    stop_environments_with_expired_access,
    stop_event_participants_environments_with_expired_access,
)
from environment.api import share_billing_account

# Setting up constants for Cache
CACHE_TIMEOUT = 60 * 60 * 24 * 15  # 15 days
CACHE_KEY_PREFIX = "pending_billing_share_"

logger = logging.getLogger(__name__)

User = get_user_model()

Training = apps.get_model("user", "Training")

DataAccessRequest = apps.get_model("project", "DataAccessRequest")

Event = apps.get_model("events", "Event")

EventApplication = apps.get_model("events", "EventApplication")

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
        owner_email = invite.owner.cloud_identity.email
        give_user_permission_to_access_billing_account(
            invite.id, owner_email, cloud_identity.email, invite.billing_account_id
        )


@receiver(post_init, sender=User)
def memoize_original_credentialing_status(instance: User, **kwargs):
    instance._original_is_credentialed = instance.is_credentialed


@receiver(post_save, sender=User)
def schedule_stop_environments_if_credentialing_revoked(instance: User, **kwargs):
    if not instance.is_credentialed and instance._original_is_credentialed:
        stop_environments_with_expired_access(instance.id)


@receiver(post_init, sender=Event)
def memoize_original_event_end_time(instance: Event, **kwargs):
    instance._original_end_date = instance.end_date


@receiver(post_save, sender=Event)
def schedule_stop_environments_if_event_finished(
    instance: Event, created: bool, **kwargs
):
    if instance._original_end_date != instance.end_date or created:
        schedule = datetime.combine(instance.end_date, datetime.min.time())
        stop_event_participants_environments_with_expired_access(
            instance.id, schedule=schedule
        )


@receiver(post_init, sender=Training)
def memoize_original_validity(instance: Training, **kwargs):
    instance._original_is_valid = instance.is_valid()


@receiver(post_save, sender=Training)
def schedule_stop_environment_if_training_accepted(instance: Training, **kwargs):
    user = instance.user

    if instance.is_valid() and not instance._original_is_valid:
        schedule = instance.process_datetime + instance.training_type.valid_duration
        stop_environments_with_expired_access(user.id, schedule=schedule)


@receiver(post_init, sender=DataAccessRequest)
def memoize_original_acceptation_status(instance: DataAccessRequest, **kwargs):
    instance._original_is_accepted = instance.is_accepted()
    instance._original_is_revoked = instance.is_revoked()


@receiver(post_save, sender=DataAccessRequest)
def schedule_stop_environment_if_data_access_request_accepted_or_revoked(
    instance: DataAccessRequest, **kwargs
):
    user = instance.requester

    request_was_accepted = instance.is_accepted() and not instance._original_is_accepted
    access_was_revoked = instance.is_revoked() and not instance._original_is_revoked
    if request_was_accepted:
        if request_was_accepted and not instance.duration:  # Indefinite access
            return
        schedule = timezone.now() + instance.duration
        stop_environments_with_expired_access(user.id, schedule=schedule)
    elif access_was_revoked:
        stop_environments_with_expired_access(user.id)


@receiver(post_init, sender=EventApplication)
def memoize_original_application_status(instance, **kwargs):
    """Store the original status to detect changes"""
    instance._original_status = getattr(instance, 'status', None)


@receiver(post_save, sender=EventApplication)
def handle_event_billing_account_on_approval(instance, **kwargs):
    """When an application is approved, share the event's billing account with the user if possible"""
    # Early return if conditions aren't met
    if not (
            instance.status == instance.EventApplicationStatus.APPROVED and
            instance._original_status != instance.EventApplicationStatus.APPROVED and
            instance.event.gcp_billing_id
    ):
        return

    event = instance.event
    user = instance.user

    # Try to share billing account immediately if user has cloud identity
    cloud_identity = CloudIdentity.objects.filter(user=user).first()

    if cloud_identity:
        # User has cloud identity, share billing account immediately
        try:
            share_billing_account(
                owner_email=event.host.cloud_identity.email,
                user_email=cloud_identity.email,
                billing_account_id=event.gcp_billing_id
            )
            logger.info(f"Billing account {event.gcp_billing_id} shared with {user.username} immediately")
        except Exception as e:
            logger.error(f"Error sharing billing account immediately: {str(e)}", exc_info=True)
    else:
        # User doesn't have cloud identity yet, store in cache
        cache_key = f"{CACHE_KEY_PREFIX}{user.id}"
        pending_shares = cache.get(cache_key, [])

        # Check if this event share is already pending
        if not any(share['event_id'] == event.id for share in pending_shares):
            pending_shares.append({
                'event_id': event.id,
                'billing_account_id': event.gcp_billing_id
            })
            cache.set(cache_key, pending_shares, timeout=CACHE_TIMEOUT)
            logger.info(f"Cached pending billing share for user {user.username}, event {event.title}")


@receiver(post_save, sender=CloudIdentity)
def process_pending_billing_shares(instance, **kwargs):
    """When a cloud identity is created, process that specific user's pending billing shares"""

    logger.info(f"Processing pending billing shares for user {instance.user.username}")

    user = instance.user
    cloud_identity_email = instance.email

    # Only get this specific user's cache
    cache_key = f"{CACHE_KEY_PREFIX}{user.id}"
    pending_shares = cache.get(cache_key, [])

    if not pending_shares:
        logger.info(f"No pending billing shares for user {user.username}")
        return

    # Collect event IDs to fetch in a single query
    event_ids = [share['event_id'] for share in pending_shares]
    events_map = {event.id: event for event in Event.objects.filter(id__in=event_ids)}

    logger.info(f"Found {len(pending_shares)} pending billing shares")

    successful_shares = []

    for share in pending_shares:
        event_id = share['event_id']
        event = events_map.get(event_id)

        if not event:
            logger.warning(f"Event {event_id} no longer exists, removing from pending shares")
            successful_shares.append(share)
            continue

        try:
            host_email = event.host.cloud_identity.email

            # Share the billing account
            share_billing_account(
                owner_email=host_email,
                user_email=cloud_identity_email,
                billing_account_id=share['billing_account_id']
            )

            # Mark as successful
            successful_shares.append(share)
            logger.info(f"Successfully shared billing account {share['billing_account_id']} with {user.username}")
        except Exception as e:
            logger.error(
                f"Error processing pending billing share for event {event_id}, user {user.username}: {str(e)}",
                exc_info=True
            )

    # Remove successful shares from cache
    if successful_shares:
        remaining_shares = [share for share in pending_shares if share not in successful_shares]
        if remaining_shares:
            cache.set(cache_key, remaining_shares, timeout=CACHE_TIMEOUT)
        else:
            cache.delete(cache_key)
