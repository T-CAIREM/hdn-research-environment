from django import forms
from django.core.exceptions import ValidationError

from environment.validators import gcp_billing_account_id_validator
from environment.entities import Region, EnvironmentType, InstanceType


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
        ("a2-highgpu-1g", "a2-highgpu-1g"),
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

    def clean(self):
        cleaned_data = super().clean()
        region = cleaned_data.get("region")
        instance_type = cleaned_data.get("instance_type")
        environment_type = cleaned_data.get("environment_type")

        self.__limit_instance_based_on_region(region, instance_type)
        self.__limit_environment_based_on_instance_type(environment_type, instance_type)

    def __limit_instance_based_on_region(self, region, instance_type):
        if (
            instance_type == InstanceType.A2_HIGHGPU_1G.value
            and region != Region.US_CENTRAL.value
        ):
            raise ValidationError(
                "GPU instances are not available in this region. Please choose other region."
            )

    def __limit_environment_based_on_instance_type(
        self, environment_type, instance_type
    ):
        if (
            instance_type == InstanceType.A2_HIGHGPU_1G.value
            and environment_type == EnvironmentType.RSTUDIO.value
        ):
            raise ValidationError(
                "GPUs are not supported by Rstudio instances. Please choose other environment type."
            )
