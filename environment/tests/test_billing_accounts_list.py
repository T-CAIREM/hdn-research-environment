"""The Billing tab links only owned accounts to the Cloud console (#188)."""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

TEMPLATE = "environment/_billing_accounts_list.html"

OWNED = {
    "id": "000000-000000-000001",
    "name": "Owned Account",
    "cloud_link": "https://console.cloud.google.com/billing/000000-000000-000001",
    "is_owner": True,
}
SHARED = {
    "id": "000000-000000-000002",
    "name": "Shared Account",
    "cloud_link": "https://console.cloud.google.com/billing/000000-000000-000002",
    "is_owner": False,
}
SHARED_NOTE = "Shared with you: select it when you create a workspace."
OPTIONAL_CREATE = "Create your own billing account (optional)"


class BillingAccountsListTemplateTests(SimpleTestCase):
    def render(self, billing_accounts_list):
        return render_to_string(
            TEMPLATE, {"billing_accounts_list": billing_accounts_list}
        )

    def test_console_link_only_for_owned_account(self):
        html = self.render([OWNED, SHARED])

        self.assertIn(f'href="{OWNED["cloud_link"]}"', html)
        self.assertIn("Manage", html)
        self.assertNotIn(SHARED["cloud_link"], html)
        self.assertIn(f'{SHARED["name"]}, {SHARED["id"]}', html)
        self.assertEqual(html.count(SHARED_NOTE), 1)
        self.assertIn("+ Billing Account", html)
        self.assertNotIn(OPTIONAL_CREATE, html)

    def test_shared_only_user_gets_no_console_link(self):
        html = self.render([SHARED])

        self.assertNotIn(SHARED["cloud_link"], html)
        self.assertNotIn("Manage", html)
        self.assertIn(SHARED_NOTE, html)
        self.assertIn(OPTIONAL_CREATE, html)
        self.assertNotIn("+ Billing Account", html)

    def test_empty_state_shows_shared_guidance_before_create_link(self):
        html = self.render([])

        shared_guidance = html.index("can take a minute to appear here")
        create_link = html.index("console.cloud.google.com/billing/create")
        self.assertLess(shared_guidance, create_link)
        self.assertIn("request Google Cloud console access", html)
