import uuid

from django.core.validators import EmailValidator
from django.db import models

from environment.validators import gcp_billing_account_id_validator


class CloudIdentity(models.Model):
    user = models.OneToOneField(
        "user.User", related_name="cloud_identity", on_delete=models.CASCADE
    )
    gcp_user_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField(
        max_length=255, unique=True, validators=[EmailValidator()]
    )
    initial_workspace_setup_done = models.BooleanField(default=False)


class BillingAccountSharingInvite(models.Model):
    owner = models.ForeignKey(
        "user.User",
        related_name="owner_billingaccountsharinginvite_set",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "user.User",
        related_name="user_billingaccountsharinginvite_set",
        on_delete=models.CASCADE,
        null=True,
    )
    user_contact_email = models.EmailField()
    billing_account_id = models.CharField(
        max_length=32, validators=[gcp_billing_account_id_validator]
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_consumed = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)


class BucketSharingInvite(models.Model):
    PERMISSIONS = (
        ("read_write", "Read and Write"),
        ("read", "Read"),
    )
    owner = models.ForeignKey(
        "user.User",
        related_name="owner_bucketsharinginvite_set",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        "user.User",
        related_name="user_bucketsharinginvite_set",
        on_delete=models.CASCADE,
        null=True,
    )
    user_contact_email = models.EmailField()
    shared_bucket_name = models.CharField(max_length=100)
    shared_workspace_name = models.CharField(max_length=100)
    permissions = models.CharField(max_length=100, choices=PERMISSIONS, default="read")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_consumed = models.BooleanField(default=False)
    is_revoked = models.BooleanField(default=False)


class Workflow(models.Model):
    user = models.ForeignKey(
        "user.User", related_name="workflows", on_delete=models.CASCADE
    )
    execution_resource_name = models.CharField(max_length=256, unique=True)
    in_progress = models.BooleanField(default=False)
