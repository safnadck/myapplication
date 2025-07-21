"""
your_app Django application initialization.
"""

from django.apps import AppConfig


class ApplicationConfig(AppConfig):
    """
    Configuration for the your_app Django application.
    """

    name = 'application'

    plugin_app = {
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'application',
                'relative_path': 'urls',
            }
        },
        'settings_config': {
            'lms.djangoapp': {
                'common': {'relative_path': 'settings'},
            }
        },
    } 