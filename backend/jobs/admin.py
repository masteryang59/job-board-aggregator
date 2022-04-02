from django.contrib import admin
from django.utils.html import format_html

from .models import Company, Job, ScrapeRun, Source


class RunInline(admin.TabularInline):
    model = ScrapeRun
    extra = 0
    max_num = 0
    can_delete = False
    fields = ["started_at", "finished_at", "status", "complete", "ingest_stats", "note"]
    readonly_fields = fields
    ordering = ["-started_at"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "base_url", "created_at"]
    inlines = [RunInline]


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "key"]
    search_fields = ["name", "key"]


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = ["id", "source", "status", "complete", "started_at", "finished_at", "summary", "note"]
    list_filter = ["source", "status", "complete"]
    readonly_fields = [f.name for f in ScrapeRun._meta.fields]

    @admin.display(description="created / updated / unchanged / closed")
    def summary(self, run):
        s = run.ingest_stats or {}
        return f"{s.get('created', 0)} / {s.get('updated', 0)} / {s.get('unchanged', 0) + s.get('seen', 0)} / {s.get('closed', 0)}"


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ["title", "company_name", "source", "workplace", "city", "salary", "posted_at", "status"]
    list_filter = ["source", "workplace", "employment_type", "seniority", ("closed_at", admin.EmptyFieldListFilter)]
    search_fields = ["title", "company_name", "external_id", "fingerprint"]
    raw_id_fields = ["duplicate_of", "company", "last_seen_run"]
    readonly_fields = ["search_vector", "content_hash", "listing_hash", "fingerprint", "first_seen_at", "last_seen_at", "detail_fetched_at"]
    date_hierarchy = "posted_at"

    @admin.display(description="salary")
    def salary(self, job):
        if job.salary_min is None:
            return "—"
        return f"{job.salary_min:,}–{job.salary_max or job.salary_min:,} {job.salary_currency}/{job.salary_period}"

    @admin.display(description="status")
    def status(self, job):
        if job.closed_at:
            return format_html('<span style="color:#999">closed</span>')
        if job.duplicate_of_id:
            return format_html("duplicate of #{}", job.duplicate_of_id)
        return "listed"

def archive_record(data=None):
    if data is None:
        return None
    return data

def archive_record(data=None):
    if data is None:
        return None
    return data