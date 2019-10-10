from __future__ import annotations

import hmac

from django.conf import settings
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from . import ingest
from .models import Job, ScrapeRun, Source
from .search import SORTS, SearchParams, listed_jobs, search
from .serializers import (
    BatchSerializer,
    FinishRunSerializer,
    JobDetailSerializer,
    JobListSerializer,
    RunSerializer,
    StartRunSerializer,
)

# --- auth for the scrapers --------------------------------------------------------


class HasIngestToken(BasePermission):
    message = "Missing or wrong ingest token (Authorization: Token <INGEST_TOKEN>)."

    def has_permission(self, request, view):
        expected = settings.INGEST_TOKEN
        if not expected:
            self.message = "Ingest is disabled: INGEST_TOKEN is not set on the backend."
            return False
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        return scheme.lower() == "token" and hmac.compare_digest(token.strip().encode(), expected.encode())


class IngestView(APIView):
    permission_classes = [HasIngestToken]
    throttle_classes: list = []

    def get_run(self, pk: int) -> ScrapeRun:
        return get_object_or_404(ScrapeRun.objects.select_related("source"), pk=pk)


class StartRunView(IngestView):
    def post(self, request):
        s = StartRunSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        run = ingest.start_run(s.validated_data["source"], s.validated_data.get("name", ""), s.validated_data.get("base_url", ""))
        return Response({"id": run.pk, "source": run.source.slug}, status=status.HTTP_201_CREATED)


class KnownView(IngestView):
    def get(self, request, slug):
        return Response({"source": slug, "known": ingest.known_listings(slug)})


class BatchView(IngestView):
    def post(self, request, pk):
        s = BatchSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            result = ingest.apply_batch(self.get_run(pk), s.validated_data["jobs"], s.validated_data["seen"])
        except ingest.RunClosed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result.as_dict())


class FinishRunView(IngestView):
    def post(self, request, pk):
        s = FinishRunSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            summary = ingest.finish_run(self.get_run(pk), **s.validated_data)
        except ingest.RunClosed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(summary)


# --- public, read-only API ------------------------------------------------------------


class CsvList(serializers.ListField):
    """Accepts ?tag=a&tag=b and ?tag=a,b alike."""

    def get_value(self, dictionary):
        if self.field_name not in dictionary:
            return serializers.empty
        values = dictionary.getlist(self.field_name) if hasattr(dictionary, "getlist") else [dictionary[self.field_name]]
        return [part.strip() for value in values for part in str(value).split(",") if part.strip()]


class SearchParamsSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    workplace = CsvList(child=serializers.ChoiceField(Job.Workplace.values), required=False, default=list)
    employment_type = CsvList(child=serializers.ChoiceField(Job.EmploymentType.values), required=False, default=list)
    seniority = CsvList(child=serializers.ChoiceField(Job.Seniority.values), required=False, default=list)
    source = CsvList(child=serializers.SlugField(), required=False, default=list)
    country = CsvList(child=serializers.RegexField(r"^[A-Za-z]{2}$"), required=False, default=list)
    tags = CsvList(child=serializers.CharField(max_length=40), required=False, default=list, max_length=10)
    salary_min = serializers.IntegerField(required=False, min_value=0, max_value=10_000_000, allow_null=True, default=None)
    posted_within = serializers.IntegerField(required=False, min_value=1, max_value=365, allow_null=True, default=None)
    has_salary = serializers.BooleanField(required=False, default=False)
    sort = serializers.ChoiceField(SORTS, required=False, default="relevance")
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)

    def validate_country(self, value):
        return [v.upper() for v in value]


class JobSearchView(APIView):
    def get(self, request):
        s = SearchParamsSerializer(data=request.query_params)
        if not s.is_valid():
            raise ValidationError(s.errors)
        params = SearchParams(**s.validated_data)
        result = search(params)
        result["results"] = JobListSerializer(result["results"], many=True).data
        result["query"] = {k: v for k, v in s.validated_data.items() if v not in ("", [], None, False)}
        return Response(result)


class JobDetailView(APIView):
    def get(self, request, pk):
        job = Job.objects.select_related("source", "company").prefetch_related("duplicates__source").filter(pk=pk).first()
        if job is None:
            raise NotFound("No such job.")
        return Response(JobDetailSerializer(job).data)


class SourcesView(APIView):
    def get(self, request):
        sources = Source.objects.annotate(
            open_jobs=Count("jobs", filter=Q(jobs__closed_at__isnull=True)),
            duplicates=Count("jobs", filter=Q(jobs__closed_at__isnull=True, jobs__duplicate_of__isnull=False)),
            closed_jobs=Count("jobs", filter=Q(jobs__closed_at__isnull=False)),
        )
        data = []
        for source in sources:
            last = source.runs.exclude(status=ScrapeRun.Status.RUNNING).first()
            data.append(
                {
                    "slug": source.slug,
                    "name": source.name,
                    "base_url": source.base_url,
                    "open_jobs": source.open_jobs,
                    "duplicates": source.duplicates,
                    "closed_jobs": source.closed_jobs,
                    "running": source.runs.filter(status=ScrapeRun.Status.RUNNING).exists(),
                    "last_run": RunSerializer(last).data if last else None,
                }
            )
        return Response({"sources": data})


class OverviewView(APIView):
    def get(self, request):
        open_jobs = Job.objects.filter(closed_at__isnull=True)
        listed = listed_jobs()
        return Response(
            {
                "listed_jobs": listed.count(),
                "open_postings": open_jobs.count(),
                "merged_duplicates": open_jobs.filter(duplicate_of__isnull=False).count(),
                "companies": listed.values("company").distinct().count(),
                "with_salary": listed.filter(salary_min__isnull=False).count(),
                "last_scraped_at": ScrapeRun.objects.filter(finished_at__isnull=False).aggregate(t=Max("finished_at"))["t"],
            }
        )


class HealthView(APIView):
    def get(self, request):
        Source.objects.exists()  # touches the database
        return Response({"ok": True})

def mask_pii(data=None):
    if data is None:
        return None
    return data