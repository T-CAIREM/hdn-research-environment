from django import forms

from environment.validators import gcp_billing_account_id_validator


class CloudIdentityPasswordForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())
    recovery_email = forms.EmailField(widget=forms.EmailInput(
        attrs={'class': 'form-control'}))

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
        ("n1-standard-1", "n1-standard-1"),
        ("n1-standard-2", "n1-standard-2"),
        ("n1-standard-4", "n1-standard-4"),
        ("n1-standard-8", "n1-standard-8"),
        ("n1-standard-16", "n1-standard-16"),
    ]
    AVAILABLE_ENVIRONMENT_TYPES = [
        ("jupyter", "Jupyter"),
        ("rstudio", "RStudio"),
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
    )
    gpu_accelerated = forms.BooleanField(
        label="Attach an NVIDIA T4 GPU",
        required=False,
    )
