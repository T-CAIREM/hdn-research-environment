import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("environment", "0011_refactor_workflow"),
    ]

    operations = [
        migrations.CreateModel(
            name="BucketSharingInvite",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("user_contact_email", models.EmailField(max_length=254)),
                (
                    "shared_bucket_name",
                    models.CharField(
                        max_length=100,
                    ),
                ),
                (
                    "shared_workspace_name",
                    models.CharField(
                        max_length=100,
                    ),
                ),
                (
                    "token",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("is_consumed", models.BooleanField(default=False)),
                ("is_revoked", models.BooleanField(default=False)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owner_bucketsharinginvite_set",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_bucketharinginvite_set",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
