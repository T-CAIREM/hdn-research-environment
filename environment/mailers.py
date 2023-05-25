from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.sites.shortcuts import get_current_site

from environment.models import BillingAccountSharingInvite


def url_domain(request):
    site = get_current_site(request)
    return f"https://{site.domain}"


def send_billing_sharing_confirmation(request, invite: BillingAccountSharingInvite):
    confirmation_path = (
        reverse("confirm_billing_account_sharing") + f"?token={invite.token}"
    )
    confirmation_url = f"{url_domain(request)}{confirmation_path}"

    return send_mail(
        "Billing Account Shared",
        f"Visit: {confirmation_url}",
        settings.DEFAULT_FROM_EMAIL,
        [invite.user_contact_email],
        fail_silently=False,
    )
