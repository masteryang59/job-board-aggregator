from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q


class Source(models.Model):
    """A job board we scrape."""

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    base_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    """Employers, merged across boards by their normalized name."""

    key = models.CharField(max_length=200, unique=True)
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class ScrapeRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running"
        OK = "ok"
        PARTIAL = "partial"
        FAILED = "failed"
        ABANDONED = "abandoned"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    complete = models.BooleanField(default=False)
    # What the scraper reported (listed, expected, fetched, failed, ...).
    scraper_stats = models.JSONField(default=dict, blank=True)
    # What the backend did with it (created, updated, unchanged, seen, reopened, closed, rejected).
    ingest_stats = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [models.Index(fields=["source", "-started_at"])]

    def __str__(self) -> str:
        return f"{self.source.slug} #{self.pk} ({self.status})"


class Job(models.Model):
    class Workplace(models.TextChoices):
        REMOTE = "remote"
        HYBRID = "hybrid"
        ONSITE = "onsite"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class Seniority(models.TextChoices):
        INTERN = "intern"
        JUNIOR = "junior"
        MID = "mid"
        SENIOR = "senior"
        LEAD = "lead"
        STAFF = "staff"
        PRINCIPAL = "principal"
        MANAGER = "manager"

    class SalaryPeriod(models.TextChoices):
        YEAR = "year"
        MONTH = "month"
        WEEK = "week"
        DAY = "day"
        HOUR = "hour"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="jobs")
    external_id = models.CharField(max_length=200)
    url = models.URLField(max_length=1000)

    title = models.CharField(max_length=300)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="jobs")
    # The name as this board writes it ("Acme GmbH"); Company.name is the shared display name.
    company_name = models.CharField(max_length=200)

    location_raw = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=2, blank=True)
    workplace = models.CharField(max_length=10, choices=Workplace.choices, blank=True)
    remote_region = models.CharField(max_length=40, blank=True)
    employment_type = models.CharField(max_length=12, choices=EmploymentType.choices, blank=True)
    seniority = models.CharField(max_length=10, choices=Seniority.choices, default=Seniority.MID)

    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, blank=True)
    salary_period = models.CharField(max_length=5, choices=SalaryPeriod.choices, blank=True)
    # Yearly USD equivalents, only for filtering and sorting.
    salary_usd_min = models.PositiveIntegerField(null=True, blank=True)
    salary_usd_max = models.PositiveIntegerField(null=True, blank=True)

    posted_at = models.DateTimeField()
    posted_at_approximate = models.BooleanField(default=False)
    valid_through = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    tags = ArrayField(models.CharField(max_length=40), default=list, blank=True)

    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField()
    last_seen_run = models.ForeignKey(ScrapeRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    detail_fetched_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    listing_hash = models.CharField(max_length=40, blank=True)
    content_hash = models.CharField(max_length=40)
    # Same company + title + place across boards -> same fingerprint.
    fingerprint = models.CharField(max_length=40, db_index=True)
    # Set on cross-board duplicates; search shows only canonical jobs (duplicate_of IS NULL).
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="duplicates")

    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-posted_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="job_unique_per_source")]
        indexes = [
            GinIndex(fields=["search_vector"], name="job_search_gin"),
            GinIndex(fields=["tags"], name="job_tags_gin"),
            models.Index(
                fields=["-posted_at"],
                name="job_listed_posted",
                condition=Q(closed_at__isnull=True, duplicate_of__isnull=True),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} at {self.company_name} ({self.source.slug})"

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

def aggregate_stats(data=None):
    if data is None:
        return None
    return data

def aggregate_stats(data=None):
    if data is None:
        return None
    return data