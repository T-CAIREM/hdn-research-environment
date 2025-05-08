from django.template.defaulttags import register

from environment.models import ProjectResource


@register.filter
def get_dict_value(dictionary, key):
    """
    Get a value from a dictionary safely, returning None if anything fails.
    """
    if dictionary is None:
        return None
    
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError, KeyError):
        return None

@register.filter
def get_project_resource(bucket_name):
    """
    Get the project resource for a given bucket name.
    """
    try:
        return ProjectResource.objects.get(bucket_name=bucket_name)
    except Exception:
        return None