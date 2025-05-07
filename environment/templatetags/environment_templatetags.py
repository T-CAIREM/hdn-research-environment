from django.template.defaulttags import register

from environment.models import ProjectResource


@register.filter
def get_dict_value(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_project_resource(bucket_name):
    """Get the project resource for a given bucket name."""
    try:
        return ProjectResource.objects.get(bucket_name=bucket_name)
    except ProjectResource.DoesNotExist:
        return None