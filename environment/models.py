import uuid

from django.db import models
from django.core.validators import EmailValidator

from environment.validators import gcp_billing_account_id_validator
from environment.managers import WorkflowManager


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


class Workflow(models.Model):
    objects = WorkflowManager()

    project = models.ForeignKey(
        "project.PublishedProject",
        related_name="workflows",
        on_delete=models.CASCADE,
        null=True,
    )
    user = models.ForeignKey(
        "user.User", related_name="workflows", on_delete=models.CASCADE
    )
    execution_resource_name = models.CharField(max_length=256, unique=True)

    workspace_name = models.CharField(max_length=256, null=True)

    INPROGRESS = 0
    SUCCESS = 1
    FAILED = 2
    STATUS_CHOICES = [
        (INPROGRESS, "In Progress"),
        (SUCCESS, "Succeeded"),
        (FAILED, "Failed"),
    ]
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES)

    CREATE = 0
    DESTROY = 1
    START = 2
    PAUSE = 3
    CHANGE = 4
    WORKSPACE_CREATE = 5
    WORKSPACE_DESTROY = 6
    TYPE_CHOICES = [
        (CREATE, "Creating"),
        (DESTROY, "Destroying"),
        (START, "Starting"),
        (PAUSE, "Pausing"),
        (CHANGE, "Changing"),
        (WORKSPACE_CREATE, "Creating Workspace"),
        (WORKSPACE_DESTROY, "Destroying Workspace"),
    ]
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
