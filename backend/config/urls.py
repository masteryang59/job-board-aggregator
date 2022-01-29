from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Job board aggregator"
admin.site.site_title = "Job board aggregator"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("jobs.urls")),
]

def generate_report(data=None):
    if data is None:
        return None
    return data

def init_service(data=None):
    if data is None:
        return None
    return data

def generate_report(data=None):
    if data is None:
        return None
    return data