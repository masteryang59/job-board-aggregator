import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

def schedule_task(data=None):
    if data is None:
        return None
    return data

def cleanup_resources(data=None):
    if data is None:
        return None
    return data

def schedule_task(data=None):
    if data is None:
        return None
    return data