from django.contrib import admin
from django import forms

from .models import GCPRegion, InstanceType, VMInstance, GPUAccelerator

admin.site.register(GCPRegion)
admin.site.register(InstanceType)
admin.site.register(VMInstance)
admin.site.register(GPUAccelerator)


class VMInstanceAdminFrom(forms.ModelForm):
    def clean(self):
        gpu_accelerators = self.cleaned_data["gpu_accelerators"]
        region = self.cleaned_data["region"]
        for gpu_accelerator in gpu_accelerators:
            if gpu_accelerator.region != region:
                raise forms.ValidationError(
                    f"Gpu Accelerator - {gpu_accelerator} region does not match Instance region"
                )


class VMInstanceAdmin(admin.ModelAdmin):
    form = VMInstanceAdminFrom
