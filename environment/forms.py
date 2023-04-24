from django import forms

from environment.validators import gcp_billing_account_id_validator


class CloudIdentityPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError(
                "The passwords don't match"
            )


class BillingAccountIdForm(forms.Form):
    billing_account_id = forms.CharField(
        label="Billing Account ID",
        max_length=20,
        validators=[gcp_billing_account_id_validator],
    )


class CreateResearchEnvironmentForm(forms.Form):
    AVAILABLE_REGIONS = [
        ("us-central1", "us-central1"),
        ("northamerica-northeast1", "northamerica-northeast1"),
        ("europe-west3", "europe-west3"),
        ("australia-southeast1", "australia-southeast1"),
    ]
    AVAILABLE_INSTANCE_TYPES = [
        ("n1-standard-1", "n1-standard-1 (1 CPU, 3.75GB RAM)"),
        ("n1-standard-2", "n1-standard-2 (2 CPU, 7.5GB RAM)"),
        ("n1-standard-4", "n1-standard-4 (4 CPU, 15GB RAM)"),
        ("n1-standard-8", "n1-standard-8 (8 CPU, 30GB RAM)"),
        ("n1-standard-16", "n1-standard-16 (16 CPU, 60GB RAM)"),
    ]
    AVAILABLE_ENVIRONMENT_TYPES = [
        ("jupyter", "Jupyter"),
        ("rstudio", "RStudio"),
    ]
    AVAILABLE_GPU_ACCELERATOR_TYPES = [
        ("", "Machine without GPU attached"),
        ("NVIDIA_TESLA_T4", "Nvidia Tesla T4 (16 GB GDDR6)"),
    ]

    region = forms.ChoiceField(label="Region", choices=AVAILABLE_REGIONS)
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

    def clean_gpu_accelerator(self):
        gpu_accelerator = self.cleaned_data.get("gpu_accelerator")
        gpu_accelerator = None if gpu_accelerator == "" else gpu_accelerator
        return gpu_accelerator
