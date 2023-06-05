from typing import Iterable

from django import forms

from environment.entities import ResearchWorkspace, InstanceType
from environment.constants import INSTANCE_TYPE_SPECIFICATION


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
    AVAILABLE_REGIONS = [
        ("us-central1", "us-central1"),
        ("northamerica-northeast1", "northamerica-northeast1"),
        ("europe-west3", "europe-west3"),
        ("australia-southeast1", "australia-southeast1"),
    ]
    billing_account_id = forms.ChoiceField(label="Billing Account")
    region = forms.ChoiceField(label="Region", choices=AVAILABLE_REGIONS)

    def __init__(self, *args, billing_accounts_list: Iterable[str], **kwargs):
        super(CreateWorkspaceForm, self).__init__(*args, **kwargs)
        self.fields["billing_account_id"].choices = [
            (billing_account["id"], billing_account["name"])
            for billing_account in billing_accounts_list
        ]


class CreateResearchEnvironmentForm(forms.Form):
    AVAILABLE_INSTANCE_TYPES = [
        ("n1-standard-2", INSTANCE_TYPE_SPECIFICATION[InstanceType.N1_STANDARD_2]),
        ("n1-standard-4", INSTANCE_TYPE_SPECIFICATION[InstanceType.N1_STANDARD_4]),
        ("n1-standard-8", INSTANCE_TYPE_SPECIFICATION[InstanceType.N1_STANDARD_8]),
        ("n1-standard-16", INSTANCE_TYPE_SPECIFICATION[InstanceType.N1_STANDARD_16]),
    ]
    AVAILABLE_ENVIRONMENT_TYPES = [
        ("jupyter", "Jupyter"),
        ("rstudio", "RStudio"),
    ]
    AVAILABLE_GPU_ACCELERATOR_TYPES = [
        ("", "Machine without GPU attached"),
        ("NVIDIA_TESLA_T4", "Nvidia Tesla T4 (16 GB GDDR6)"),
    ]

    workspace_id = forms.ChoiceField(label="Workspace")
    instance_type = forms.ChoiceField(
        label="Instance type",
        choices=AVAILABLE_INSTANCE_TYPES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    environment_type = forms.ChoiceField(
        label="Environment type",
        choices=AVAILABLE_ENVIRONMENT_TYPES,
        widget=forms.RadioSelect(attrs={"class": "environment-type"}),
    )
    persistent_disk = forms.IntegerField(
        label="Persistent data disk size [GB]",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "max": 64000}
        ),
        initial=0,
    )
    gpu_accelerator = forms.ChoiceField(
        label="GPU Accelerator",
        choices=AVAILABLE_GPU_ACCELERATOR_TYPES,
        widget=forms.Select(attrs={"class": "form-control"}),
        required=False,
    )

    def __init__(self, *args, workspace_list: Iterable[ResearchWorkspace], **kwargs):
        super(CreateResearchEnvironmentForm, self).__init__(*args, **kwargs)
        self.fields["workspace_id"].choices = [
            (workspace.gcp_project_id, workspace.gcp_project_id)
            for workspace in workspace_list
        ]

    def clean_gpu_accelerator(self):
        gpu_accelerator = self.cleaned_data.get("gpu_accelerator")
        gpu_accelerator = None if gpu_accelerator == "" else gpu_accelerator
        return gpu_accelerator


class ShareBillingAccountForm(forms.Form):
    user_email = forms.EmailField(label="User E-Mail")
