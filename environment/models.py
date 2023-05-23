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


class Workflow(models.Model):
    objects = WorkflowManager()

    project = models.ForeignKey(
        "project.PublishedProject", related_name="workflows", on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        "user.User", related_name="workflows", on_delete=models.CASCADE
    )
    execution_resource_name = models.CharField(max_length=256, unique=True)

    workspace_name = models.CharField(max_length=256)

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
    TYPE_CHOICES = [
        (CREATE, "Creating"),
        (DESTROY, "Destroying"),
        (START, "Starting"),
        (PAUSE, "Pausing"),
        (CHANGE, "Changing"),
    ]
    type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
