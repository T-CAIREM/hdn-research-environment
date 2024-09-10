import uuid

from django.core.validators import EmailValidator
from django.db import models
from enum import Enum

from environment.validators import gcp_billing_account_id_validator

# GCP Compute Machine Choices
MACHINE_FAMILY_CHOICES = (
    ("general", "General Purpose"),
    ("compute", "Compute Optimized"),
    ("memory", "Memory Optimized"),
    ("storage", "Storage Optimized"),
    ("accelerator", "Accelerator Optimized"),
)

# GCP Machine Type Choices
MACHINE_TYPE_CHOICES = (
    ("standard", "Standard"),
    ("highmem", "High Memory"),
    ("ultramem", "Ultra Memory"),
    ("megamem", "Mega Memory"),
    ("hypermem", "High Memory"),
    ("highcpu", "High CPU"),
    ("highgpu", "High GPU"),
    ("megagpu", "Mega GPU"),
    ("ultragpu", "Ultra GPU"),
)

# GCP  GPU memory types
GPU_MEMORY_TYPES = {
    ("GDDR5", "GDDR5"),
    ("GDDR6", "GDDR6"),
    ("HBM2", "HBM2"),
    ("HBM2e", "HBM2e"),
    ("HBM3", "HBM3"),
}


class CloudGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()

    def __str__(self):
        return self.name


class CloudIdentity(models.Model):
    user = models.OneToOneField(
        "user.User", related_name="cloud_identity", on_delete=models.CASCADE
    )
    gcp_user_id = models.CharField(max_length=50, unique=True)
    email = models.EmailField(
        max_length=255, unique=True, validators=[EmailValidator()]
    )
    initial_workspace_setup_done = models.BooleanField(default=False)
    user_groups = models.ManyToManyField(CloudGroup)


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


class InstanceType(models.Model):
    family = models.CharField(max_length=32, choices=MACHINE_FAMILY_CHOICES)
    value = models.CharField(max_length=32)

    def __str__(self):
        return f"{self.family} {self.value}"

    class Meta:
        unique_together = ("family", "value")


# This Region has been added to be used for the VMInstance model.
# The region entity is still being used and will be phased out slowly.
class GCPRegion(models.Model):
    region = models.CharField(max_length=32)

    def __str__(self):
        return self.region


class GPUAccelerator(models.Model):
    name = models.CharField(max_length=64)
    memory_per_core = models.IntegerField()
    region = models.ForeignKey(GCPRegion, on_delete=models.CASCADE)
    price = models.FloatField()
    memory_type = models.CharField(max_length=32, choices=GPU_MEMORY_TYPES)

    def __str__(self):
        return f"{self.name.replace('-', ' ').title()} ({self.memory_per_core} GB {self.memory_type}) - {self.region.region}"


class VMInstance(models.Model):
    instance_type = models.ForeignKey(InstanceType, on_delete=models.CASCADE)
    machine_type = models.CharField(max_length=32, choices=MACHINE_TYPE_CHOICES)
    cpu = models.IntegerField()
    memory = models.FloatField()
    region = models.ForeignKey(GCPRegion, on_delete=models.CASCADE)
    price = models.FloatField()
    gpu_accelerators = models.ManyToManyField(GPUAccelerator, blank=True)

    def get_instance_value(self):
        return f"{self.instance_type.value}-{self.machine_type}-{self.cpu}"

    def get_instance_key(self):
        return (
            f"{self.instance_type.value.upper()}_{self.machine_type.upper()}_{self.cpu}"
        )

    def __str__(self):
        return f"{self.instance_type.value.upper()}, {self.cpu} CPU {self.memory} GB RAM - {self.region.region}"

    class Meta:
        unique_together = ("instance_type", "machine_type", "region", "cpu")
