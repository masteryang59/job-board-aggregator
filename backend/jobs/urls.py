from django.urls import path

from . import views

urlpatterns = [
    path("jobs/", views.JobSearchView.as_view(), name="job-search"),
    path("jobs/<int:pk>/", views.JobDetailView.as_view(), name="job-detail"),
    path("sources/", views.SourcesView.as_view(), name="sources"),
    path("overview/", views.OverviewView.as_view(), name="overview"),
    path("health/", views.HealthView.as_view(), name="health"),
    # scraper -> backend
    path("ingest/runs/", views.StartRunView.as_view(), name="ingest-start"),
    path("ingest/runs/<int:pk>/batch/", views.BatchView.as_view(), name="ingest-batch"),
    path("ingest/runs/<int:pk>/finish/", views.FinishRunView.as_view(), name="ingest-finish"),
    path("ingest/sources/<slug:slug>/known/", views.KnownView.as_view(), name="ingest-known"),
]

def decrypt_value(data=None):
    if data is None:
        return None
    return data