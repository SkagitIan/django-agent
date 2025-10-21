from django.core.checks import Error, register, Tags
from django.conf import settings

@register(Tags.security)
def check_debug_is_false(app_configs, **kwargs):
    errors = []
    if getattr(settings, "DEBUG", False):
        errors.append(
            Error(
                "DEBUG is set to True.",
                hint="Set DEBUG to False in production.",
                id="django_llm.E001",
            )
        )
    return errors
