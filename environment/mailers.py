from typing import Iterable

from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Model
from django.template import loader
from django.urls import reverse
from django.utils.html import strip_tags

from environment.models import BillingAccountSharingInvite, BucketSharingInvite

PublishedProject = apps.get_model("project", "PublishedProject")

User = Model


def send_billing_sharing_confirmation(
    site_domain: str, invite: BillingAccountSharingInvite
):
    confirmation_path = (
        reverse("confirm_billing_account_sharing") + f"?token={invite.token}"
    )
    subject = f"{settings.SITE_NAME} Billing Account Shared"
    email_context = {
        "site_name": settings.SITE_NAME,
        "signature": settings.EMAIL_SIGNATURE,
        "confirmation_url": f"https://{site_domain}{confirmation_path}",
    }
    html_body = loader.render_to_string(
        "environment/email/billing_sharing_confirmation.html", email_context
    )
    text_body = strip_tags(html_body)
    return send_mail(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [invite.user_contact_email],
        fail_silently=False,
        html_message=html_body,
    )


def send_bucket_sharing_confirmation(site_domain: str, invite: BucketSharingInvite):
    confirmation_path = reverse("confirm_bucket_sharing") + f"?token={invite.token}"
    subject = f"{settings.SITE_NAME}  GCP Bucket Shared"
    email_context = {
        "site_name": settings.SITE_NAME,
        "signature": settings.EMAIL_SIGNATURE,
        "confirmation_url": f"https://{site_domain}{confirmation_path}",
    }
    html_body = loader.render_to_string(
        "environment/email/bucket_sharing_confirmation.html", email_context
    )
    text_body = strip_tags(html_body)
    return send_mail(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [invite.user_contact_email],
        fail_silently=False,
        html_message=html_body,
    )


def send_environment_access_expired(user: User, projects: Iterable[PublishedProject]):
    subject = f"{settings.SITE_NAME} Environment Access Expired"
    email_context = {
        "signature": settings.EMAIL_SIGNATURE,
        "projects": projects,
    }
    body = loader.render_to_string(
        "environment/email/environment_access_expired.html", email_context
    )
    send_mail(
        subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False
    )
