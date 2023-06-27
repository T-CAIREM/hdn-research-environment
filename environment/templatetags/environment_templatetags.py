from django.template.defaulttags import register


@register.filter(name="get_instance_type")
def get_instance_type(dictionary, environment):
    if environment:
        return dictionary.get(environment.instance_type)
