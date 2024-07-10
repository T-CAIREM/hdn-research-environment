from django.contrib import admin

from .models import GCPRegion, InstanceType, VMInstance

admin.site.register(GCPRegion)
admin.site.register(InstanceType)
admin.site.register(VMInstance)
