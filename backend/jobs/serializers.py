from __future__ import annotations

from rest_framework import serializers

from .models import Job, ScrapeRun, Source
from .normalize import GENDER_MARKERS

# --- ingest (scraper -> backend) ------------------------------------------------


class JobInSerializer(serializers.Serializer):
    """One posting as the scrapers send it (see scrapers/src/normalize.js buildPosting)."""

    source = serializers.SlugField(max_length=40)
    external_id = serializers.CharField(max_length=200)
    url = serializers.URLField(max_length=1000)
    title = serializers.CharField(max_length=300)
    company = serializers.CharField(max_length=200)
    location_raw = serializers.CharField(max_length=300, required=False, allow_null=True, allow_blank=True)
    city = serializers.CharField(max_length=120, required=False, allow_null=True, allow_blank=True)
    country = serializers.CharField(min_length=2, max_length=2, required=False, allow_null=True)
    workplace = serializers.ChoiceField(Job.Workplace.choices, required=False, allow_null=True)
    remote_region = serializers.CharField(max_length=40, required=False, allow_null=True, allow_blank=True)
    employment_type = serializers.ChoiceField(Job.EmploymentType.choices, required=False, allow_null=True)
    salary_min = serializers.IntegerField(min_value=1, max_value=10_000_000, required=False, allow_null=True)
    salary_max = serializers.IntegerField(min_value=1, max_value=10_000_000, required=False, allow_null=True)
    salary_currency = serializers.RegexField(r"^[A-Za-z]{3}$", required=False, allow_null=True)
    salary_period = serializers.ChoiceField(Job.SalaryPeriod.choices, required=False, allow_null=True)
    posted_at = serializers.DateTimeField(required=False, allow_null=True)
    posted_at_approximate = serializers.BooleanField(required=False, default=False)
    valid_through = serializers.DateTimeField(required=False, allow_null=True)
    description = serializers.CharField(max_length=60_000, required=False, allow_blank=True, trim_whitespace=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=60), max_length=40, required=False)
    listing_hash = serializers.CharField(max_length=40, required=False, allow_null=True, allow_blank=True)

    def validate(self, attrs):
        lo, hi = attrs.get("salary_min"), attrs.get("salary_max")
        if lo is not None and hi is not None and hi < lo:
            raise serializers.ValidationError({"salary_max": "must be >= salary_min"})
        if (lo is not None or hi is not None) and not (attrs.get("salary_currency") and attrs.get("salary_period")):
            raise serializers.ValidationError({"salary_currency": "a salary needs a currency and a period"})
        if lo is None and hi is not None:
            attrs["salary_min"] = hi
        return attrs


class StartRunSerializer(serializers.Serializer):
    source = serializers.SlugField(max_length=40)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    base_url = serializers.URLField(required=False, allow_blank=True)


class BatchSerializer(serializers.Serializer):
    # Postings are validated one by one in ingest.apply_batch, so one bad posting
    # is reported back instead of failing the whole batch.
    jobs = serializers.ListField(child=serializers.DictField(), max_length=500, required=False, default=list)
    seen = serializers.ListField(child=serializers.CharField(max_length=200), max_length=5000, required=False, default=list)


class FinishRunSerializer(serializers.Serializer):
    status = serializers.ChoiceField(["ok", "partial", "failed"])
    complete = serializers.BooleanField()
    stats = serializers.DictField(required=False, default=dict)
    errors = serializers.ListField(child=serializers.CharField(max_length=2000), max_length=200, required=False, default=list)
    force = serializers.BooleanField(required=False, default=False)


# --- public API (backend -> frontend) -------------------------------------------


class SourceRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ["slug", "name"]


def salary_of(job: Job) -> dict | None:
    if job.salary_min is None:
        return None
    return {
        "min": job.salary_min,
        "max": job.salary_max or job.salary_min,
        "currency": job.salary_currency,
        "period": job.salary_period,
        "usd_annual_min": job.salary_usd_min,
        "usd_annual_max": job.salary_usd_max,
    }


class JobListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    company = serializers.CharField(source="company.name")
    source = SourceRefSerializer()
    salary = serializers.SerializerMethodField()
    snippet = serializers.SerializerMethodField()
    also_on = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id", "title", "company", "city", "country", "workplace", "remote_region", "location_raw",
            "employment_type", "seniority", "salary", "posted_at", "posted_at_approximate", "tags", "source",
            "url", "snippet", "also_on",
        ]

    def get_title(self, job):
        # "DevOps Engineer (m/f/d)" -> "DevOps Engineer"; the stored title keeps the board's wording.
        return " ".join(GENDER_MARKERS.sub(" ", job.title).split()) or job.title

    def get_salary(self, job):
        return salary_of(job)

    def get_snippet(self, job):
        # Search results carry a highlighted, HTML-escaped headline (see search.py).
        headline = getattr(job, "headline_html", None)
        if headline:
            return headline
        from django.utils.html import escape

        text = " ".join(job.description.split())
        return escape(text[:220] + ("…" if len(text) > 220 else ""))

    def get_also_on(self, job):
        return [{"source": d.source.slug, "name": d.source.name, "url": d.url} for d in job.duplicates.all() if d.closed_at is None]


class JobDetailSerializer(JobListSerializer):
    canonical_id = serializers.IntegerField(source="duplicate_of_id", allow_null=True)
    is_open = serializers.BooleanField()

    class Meta(JobListSerializer.Meta):
        fields = JobListSerializer.Meta.fields + [
            "description", "valid_through", "first_seen_at", "last_seen_at", "closed_at", "is_open", "canonical_id",
        ]

    def get_snippet(self, job):
        return None


class RunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScrapeRun
        fields = ["id", "status", "complete", "started_at", "finished_at", "scraper_stats", "ingest_stats", "note"]

def subscribe_topic(data=None):
    if data is None:
        return None
    return data