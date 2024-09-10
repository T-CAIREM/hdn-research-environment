from typing import Iterable

from django import forms
from django.apps import apps
from django.utils.safestring import mark_safe
from django.core.validators import RegexValidator
from django.contrib.admin.widgets import FilteredSelectMultiple

from environment.entities import (
    ResearchWorkspace,
    SharedWorkspace,
    SharedBucket,
)

from django.conf import settings

from environment.models import (
    BucketSharingInvite,
    VMInstance,
    CloudGroup,
    GPUAccelerator,
)

PublishedProject = apps.get_model("project", "PublishedProject")
User = apps.get_model("user", "User")

AVAILABLE_REGIONS = [
    ("us-central1", "us-central1"),
    ("northamerica-northeast1", "northamerica-northeast1"),
    ("europe-west3", "europe-west3"),
    ("australia-southeast1", "australia-southeast1"),
]


class CloudIdentityPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())
    recovery_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("The passwords don't match")


class CreateWorkspaceForm(forms.Form):
    billing_account_id = forms.ChoiceField(label="Billing Account")
    region = forms.ChoiceField(label="Region", choices=AVAILABLE_REGIONS)

    def __init__(self, *args, billing_accounts_list: Iterable[str], **kwargs):
        super(CreateWorkspaceForm, self).__init__(*args, **kwargs)
        self.fields["billing_account_id"].choices = [
            (
                billing_account["id"],
                f"{billing_account['name']}, {billing_account['id']}",
            )
            for billing_account in billing_accounts_list
        ]


class CreateResearchEnvironmentForm(forms.Form):
    AVAILABLE_ENVIRONMENT_TYPES = [
        ("jupyter", "Jupyter"),
        ("rstudio", "RStudio"),
    ]

    workspace_project_id = forms.CharField(
        label="Selected workspace",
        help_text=mark_safe(
            'Go <a href="/environments/">back</a> to select a different workspace. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )
    workspace_region = forms.CharField(widget=forms.HiddenInput())
    project_id = forms.ChoiceField(label="Project")
    machine_type = forms.ModelChoiceField(
        label="Instance type",
        queryset=VMInstance.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    environment_type = forms.ChoiceField(
        label="Environment type",
        choices=AVAILABLE_ENVIRONMENT_TYPES,
        widget=forms.RadioSelect(attrs={"class": "environment-type"}),
    )
    disk_size = forms.IntegerField(
        label="Persistent data disk size [GB]",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "max": 64000}
        ),
        initial=0,
    )
    gpu_accelerator = forms.ModelChoiceField(
        label="GPU Accelerator",
        queryset=GPUAccelerator.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )
    shared_bucket = forms.ChoiceField(
        label="Shared Bucket",
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    def __init__(
        self,
        *args,
        selected_workspace: ResearchWorkspace,
        projects_list: Iterable[PublishedProject],
        buckets_list: Iterable[SharedBucket],
        **kwargs,
    ):
        super(CreateResearchEnvironmentForm, self).__init__(*args, **kwargs)
        self.fields["workspace_project_id"].initial = selected_workspace.gcp_project_id
        self.fields["workspace_project_id"].disabled = True
        self.fields["workspace_region"].initial = selected_workspace.region.value

        self.fields["project_id"].choices = [
            (project.id, project) for project in projects_list
        ]
        self.fields["machine_type"].queryset = VMInstance.objects.filter(
            region__region=selected_workspace.region.value
        )

        self.fields["shared_bucket"].choices = [
            ("", "Machine without shared bucket attached")
        ] + [(bucket.name, bucket.name) for bucket in buckets_list]

    def clean_gpu_accelerator(self):
        gpu_accelerator = self.cleaned_data.get("gpu_accelerator")
        return None if gpu_accelerator == "" else gpu_accelerator


class ShareBillingAccountForm(forms.Form):
    user_email = forms.EmailField(label="User E-Mail")


class CreateSharedWorkspaceForm(forms.Form):
    billing_account_id = forms.ChoiceField(label="Billing Account")

    def __init__(self, *args, billing_accounts_list: Iterable[str], **kwargs):
        super(CreateSharedWorkspaceForm, self).__init__(*args, **kwargs)
        self.fields["billing_account_id"].choices = [
            (
                billing_account["id"],
                f"{billing_account['name']}, {billing_account['id']}",
            )
            for billing_account in billing_accounts_list
        ]


class CreateSharedBucketForm(forms.Form):
    workspace_project_id = forms.CharField(
        label="Selected workspace",
        help_text=mark_safe(
            'Go <a href="/environments/">back</a> to select a different shared workspace. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )

    user_defined_bucket_name = forms.CharField(
        max_length=32,
        label="Bucket name",
        validators=[RegexValidator(r"^[a-z0-9-_]+$")],
        error_messages={
            "invalid": "Enter a value that consists only of lowercase letters, digits, dashes or underscores"
        },
        help_text="<p>Note: Should consists only of lowercase letters, digits, dashes and underscores</p>",
    )
    region = forms.ChoiceField(label="Region", choices=AVAILABLE_REGIONS)

    def __init__(
        self,
        *args,
        selected_shared_workspace: SharedWorkspace,
        **kwargs,
    ):
        super(CreateSharedBucketForm, self).__init__(*args, **kwargs)
        self.fields[
            "workspace_project_id"
        ].initial = selected_shared_workspace.gcp_project_id
        self.fields["workspace_project_id"].disabled = True


class BucketSharingForm(forms.Form):
    PERMISSIONS = [
        ("read", "Read"),
        ("read_write", "Read and Write"),
    ]

    user_email = forms.EmailField(label="User E-Mail")
    user_permissions = forms.ChoiceField(label="User permissions", choices=PERMISSIONS)

    def __init__(
        self,
        *args,
        invitation_owner: User,
        shared_bucket_name: str,
        **kwargs,
    ):
        super(BucketSharingForm, self).__init__(*args, **kwargs)
        self.invitation_owner = invitation_owner
        self.shared_bucket_name = shared_bucket_name

    def clean(self):
        cleaned_data = super(BucketSharingForm, self).clean()
        user_email = cleaned_data.get("user_email")
        if BucketSharingInvite.objects.filter(
            owner=self.invitation_owner,
            user_contact_email=user_email,
            is_consumed=False,
            shared_bucket_name=self.shared_bucket_name,
        ):
            raise forms.ValidationError(
                "Invitation has been already sent to this email address"
            )


class AddUserToCloudGroupForm(forms.Form):
    username = forms.CharField(
        label="Selected User",
        help_text=mark_safe(
            'Go <a href="/environments/console/group">back</a> to select a different user. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )

    cloud_group = forms.MultipleChoiceField(
        label="Google Cloud Group",
    )

    def __init__(
        self,
        *args,
        user: User,
        cloud_group_list: Iterable[CloudGroup],
        **kwargs,
    ):
        super(AddUserToCloudGroupForm, self).__init__(*args, **kwargs)
        self.fields["username"].initial = user.username
        self.fields["username"].disabled = True
        self.fields["cloud_group"].choices = [
            (cloud_group.id, cloud_group.name)
            for cloud_group in cloud_group_list
            if cloud_group not in user.cloud_identity.user_groups.all()
        ]


class RemoveUserFromCloudGroupForm(forms.Form):
    username = forms.CharField(
        label="Selected User",
        help_text=mark_safe(
            'Go <a href="/environments/console/group">back</a> to select a different user. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )

    cloud_group = forms.MultipleChoiceField(
        label="User Google Cloud Groups",
    )

    def __init__(
        self,
        *args,
        user: User,
        **kwargs,
    ):
        super(RemoveUserFromCloudGroupForm, self).__init__(*args, **kwargs)
        self.fields["username"].initial = user.username
        self.fields["username"].disabled = True
        self.fields["cloud_group"].choices = [
            (cloud_group.id, cloud_group.name)
            for cloud_group in user.cloud_identity.user_groups.all()
        ]


class AddCloudGroupForm(forms.Form):
    name = forms.CharField(
        max_length=50,
        label="Cloud Group Name",
        validators=[RegexValidator(r"^[a-z0-9-_]+$")],
        error_messages={
            "invalid": "Enter a value that consists only of lowercase letters, digits, dashes or underscores"
        },
        help_text="<p>Note: Should consists only of lowercase letters, digits, dashes and underscores</p>",
    )

    description = forms.CharField(
        label="Cloud Group Description",
    )


class AddRolesToCloudGroupForm(forms.Form):
    cloud_group_name = forms.CharField(
        label="Selected Group",
        help_text=mark_safe(
            'Go <a href="/environments/console/group">back</a> to select a different group. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )
    roles_list = forms.MultipleChoiceField(
        label="Roles", widget=FilteredSelectMultiple("Roles", is_stacked=True)
    )

    class Media:
        css = {
            "all": ("admin/css/widgets.css",),
        }
        js = ("/admin/jsi18n",)

    def __init__(
        self,
        *args,
        cloud_group_name: str,
        available_roles: list,
        **kwargs,
    ):
        super(AddRolesToCloudGroupForm, self).__init__(*args, **kwargs)
        self.fields["cloud_group_name"].initial = cloud_group_name
        self.fields["cloud_group_name"].disabled = True
        self.fields["roles_list"].choices = [
            (role.full_name, role.title) for role in available_roles
        ]


class RemoveRolesFromCloudGroupForm(forms.Form):
    cloud_group_name = forms.CharField(
        label="Selected Group",
        help_text=mark_safe(
            'Go <a href="/environments/console/group">back</a> to select a different group. <br>'
        ),
        widget=forms.TextInput(attrs={"class": "text-muted"}),
    )
    roles_list = forms.MultipleChoiceField(
        widget=FilteredSelectMultiple("Roles", is_stacked=True)
    )

    class Media:
        css = {
            "all": ("admin/css/widgets.css",),
        }
        js = ("/admin/jsi18n",)

    def __init__(
        self,
        *args,
        cloud_group_name: str,
        available_roles: list,
        **kwargs,
    ):
        super(RemoveRolesFromCloudGroupForm, self).__init__(*args, **kwargs)
        self.fields["cloud_group_name"].initial = cloud_group_name
        self.fields["cloud_group_name"].disabled = True
        self.fields["roles_list"].choices = [
            (role.full_name, role.title) for role in available_roles
        ]


class UpdateWorkspaceBillingAccountForm(forms.Form):
    billing_account_id = forms.ChoiceField(label="Choose Billing Account")
    workspace_project_id = forms.CharField(widget=forms.HiddenInput())

    def __init__(
        self,
        *args,
        workspace_project_id: str,
        billing_accounts_list: Iterable[str],
        **kwargs,
    ):
        super(UpdateWorkspaceBillingAccountForm, self).__init__(*args, **kwargs)
        self.fields["workspace_project_id"].initial = workspace_project_id
        self.fields["billing_account_id"].choices = [
            (
                billing_account["id"],
                f"{billing_account['name']}, {billing_account['id']}",
            )
            for billing_account in billing_accounts_list
        ]
