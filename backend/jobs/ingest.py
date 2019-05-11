"""Turning scraper batches into Jobs: upsert, change detection, closing, de-duplication.

A scrape is a run: start -> any number of batches -> finish. Batches carry full
postings (new or changed listings) and `seen` ids (listings the scraper saw but
didn't re-fetch because their listing hash was unchanged). Finishing a complete
run closes the source's jobs that weren't seen in it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import timedelta

from django.conf import settings
from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import F, Func, Q, TextField, Value
from django.utils import timezone

from . import normalize, skills
from .models import Company, Job, ScrapeRun, Source
from .serializers import JobInSerializer

log = logging.getLogger(__name__)

# Fields that make up a job's content; if none change, the job is "unchanged".
CONTENT_FIELDS = [
    "url", "title", "company_name", "location_raw", "city", "country", "workplace", "remote_region",
    "employment_type", "salary_min", "salary_max", "salary_currency", "salary_period", "valid_through",
    "description", "tags",
]


class RunClosed(Exception):
    """The run was already finished or abandoned."""


@dataclass
class BatchResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    reopened: int = 0
    seen: int = 0
    rejected: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def search_vector():
    tags_text = Func(F("tags"), Value(" "), function="array_to_string", output_field=TextField())
    return (
        SearchVector("title", weight="A", config="english")
        + SearchVector("company_name", weight="A", config="english")
        + SearchVector(tags_text, weight="B", config="english")
        + SearchVector("city", weight="C", config="english")
        + SearchVector("description", weight="D", config="english")
    )


def _content_hash(values: dict) -> str:
    payload = {k: values.get(k) for k in CONTENT_FIELDS}
    if payload.get("valid_through"):
        payload["valid_through"] = payload["valid_through"].isoformat()
    return hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def start_run(slug: str, name: str, base_url: str = "") -> ScrapeRun:
    with transaction.atomic():
        source, _ = Source.objects.update_or_create(slug=slug, defaults={"name": name or slug, "base_url": base_url})
        # Only one run per source at a time: a new one means the previous scraper died.
        ScrapeRun.objects.filter(source=source, status=ScrapeRun.Status.RUNNING).update(
            status=ScrapeRun.Status.ABANDONED, finished_at=timezone.now(), note="superseded by a newer run"
        )
        return ScrapeRun.objects.create(source=source)


def known_listings(slug: str) -> dict[str, str]:
    """external_id -> listing_hash for open jobs whose details are fresh enough to skip."""
    fresh_after = timezone.now() - timedelta(hours=settings.DETAIL_MAX_AGE_HOURS)
    rows = Job.objects.filter(
        source__slug=slug, closed_at__isnull=True, detail_fetched_at__gte=fresh_after
    ).exclude(listing_hash="")
    return dict(rows.values_list("external_id", "listing_hash"))


def _companies_for(names: list[str]) -> dict[str, Company]:
    by_key: dict[str, str] = {}
    for name in names:
        by_key.setdefault(normalize.company_key(name) or name.lower(), name)
    existing = {c.key: c for c in Company.objects.filter(key__in=by_key)}
    missing = [Company(key=k, name=_display_name(n)) for k, n in by_key.items() if k not in existing]
    if missing:
        Company.objects.bulk_create(missing, ignore_conflicts=True)
        existing = {c.key: c for c in Company.objects.filter(key__in=by_key)}
    return {name: existing[normalize.company_key(name) or name.lower()] for name in names}


def _display_name(name: str) -> str:
    """'Northwind Analytics GmbH' -> 'Northwind Analytics' (keeps the board's capitalisation)."""
    words = name.split()
    while len(words) > 1 and normalize.company_key(words[-1]) in normalize.LEGAL_SUFFIXES | {""}:
        words.pop()
    return " ".join(words).rstrip(",")


def _values_from(data: dict) -> dict:
    tags = skills.extract_tags(data.get("tags") or [], data["title"], data.get("description", ""))
    workplace = data.get("workplace") or ""
    values = {
        "url": data["url"],
        "title": data["title"],
        "company_name": data["company"],
        "location_raw": data.get("location_raw") or "",
        "city": data.get("city") or "",
        "country": (data.get("country") or "").upper(),
        "workplace": workplace,
        "remote_region": data.get("remote_region") or "",
        "employment_type": data.get("employment_type") or "",
        "salary_min": data.get("salary_min"),
        "salary_max": data.get("salary_max"),
        "salary_currency": (data.get("salary_currency") or "").upper(),
        "salary_period": data.get("salary_period") or "",
        "valid_through": data.get("valid_through"),
        "description": data.get("description") or "",
        "tags": tags,
        "listing_hash": data.get("listing_hash") or "",
        "seniority": normalize.seniority(data["title"], data.get("employment_type")),
        "fingerprint": normalize.fingerprint(data["company"], data["title"], workplace, data.get("city"), data.get("country")),
    }
    values["salary_usd_min"] = normalize.annual_usd(values["salary_min"], values["salary_currency"], values["salary_period"])
    values["salary_usd_max"] = normalize.annual_usd(
        values["salary_max"] or values["salary_min"], values["salary_currency"], values["salary_period"]
    )
    values["content_hash"] = _content_hash(values)
    return values


def apply_batch(run: ScrapeRun, jobs: list[dict], seen: list[str]) -> BatchResult:
    result = BatchResult()
    valid: dict[str, dict] = {}
    for index, raw in enumerate(jobs):
        serializer = JobInSerializer(data=raw)
        if not serializer.is_valid():
            # Plain data: DRF's ReturnDict can't be deep-copied (asdict does that).
            errors = json.loads(json.dumps(serializer.errors))
            external_id = raw.get("external_id", "") if isinstance(raw, dict) else ""
            result.rejected.append({"index": index, "external_id": str(external_id)[:200], "errors": errors})
            continue
        data = serializer.validated_data
        if data["source"] != run.source.slug:
            result.rejected.append({"index": index, "external_id": data["external_id"], "errors": {"source": ["does not match the run"]}})
            continue
        valid[data["external_id"]] = data  # a repeated id in one batch: last one wins

    with transaction.atomic():
        run = ScrapeRun.objects.select_for_update().select_related("source").get(pk=run.pk)
        if run.status != ScrapeRun.Status.RUNNING:
            raise RunClosed(f"run {run.pk} is {run.status}")
        now = timezone.now()
        existing = {
            j.external_id: j
            for j in Job.objects.select_for_update().filter(source=run.source, external_id__in=list(valid))
        }
        companies = _companies_for([d["company"] for d in valid.values()])
        to_create: list[Job] = []
        to_update: list[Job] = []
        touched_fingerprints: set[str] = set()
        vector_ids: list[int] = []

        for external_id, data in valid.items():
            values = _values_from(data)
            posted, approximate = data.get("posted_at"), data.get("posted_at_approximate", False)
            job = existing.get(external_id)
            if job is None:
                to_create.append(
                    Job(
                        source=run.source,
                        external_id=external_id,
                        company=companies[data["company"]],
                        posted_at=posted or now,
                        posted_at_approximate=bool(approximate) or posted is None,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_seen_run=run,
                        detail_fetched_at=now,
                        **values,
                    )
                )
                touched_fingerprints.add(values["fingerprint"])
                result.created += 1
                continue

            reopened = job.closed_at is not None
            changed = job.content_hash != values["content_hash"]
            job.last_seen_at = now
            job.last_seen_run = run
            job.detail_fetched_at = now
            job.listing_hash = values["listing_hash"]
            job.closed_at = None
            # "30+ days ago" only says "at least 30 days": never move a known date later because of it.
            if posted and not (approximate and job.posted_at and job.posted_at <= posted):
                job.posted_at, job.posted_at_approximate = posted, bool(approximate)
            if changed:
                touched_fingerprints.add(job.fingerprint)
                for key, value in values.items():
                    setattr(job, key, value)
                job.company = companies[data["company"]]
                result.updated += 1
            else:
                result.unchanged += 1
            if reopened:
                result.reopened += 1
            if changed or reopened:
                touched_fingerprints.add(job.fingerprint)
                vector_ids.append(job.pk)
            to_update.append(job)

        Job.objects.bulk_create(to_create)
        if to_update:
            Job.objects.bulk_update(
                to_update,
                ["last_seen_at", "last_seen_run", "detail_fetched_at", "listing_hash", "closed_at", "posted_at",
                 "posted_at_approximate", "company", "content_hash", "fingerprint", "seniority", "salary_usd_min",
                 "salary_usd_max", *CONTENT_FIELDS],
            )

        if seen:
            seen_qs = Job.objects.filter(source=run.source, external_id__in=seen)
            reopened_fps = list(seen_qs.filter(closed_at__isnull=False).values_list("fingerprint", flat=True))
            result.reopened += len(reopened_fps)
            touched_fingerprints.update(reopened_fps)
            result.seen = seen_qs.update(last_seen_at=now, last_seen_run=run, closed_at=None)

        vector_ids += [j.pk for j in to_create]
        if vector_ids:
            Job.objects.filter(pk__in=vector_ids).update(search_vector=search_vector())
        regroup(touched_fingerprints)

        stats = run.ingest_stats or {}
        for key in ("created", "updated", "unchanged", "reopened", "seen"):
            stats[key] = stats.get(key, 0) + getattr(result, key)
        stats["rejected"] = stats.get("rejected", 0) + len(result.rejected)
        run.ingest_stats = stats
        if result.rejected:
            run.errors = (run.errors + [f"rejected {r['external_id']}: {r['errors']}" for r in result.rejected])[:100]
        run.save(update_fields=["ingest_stats", "errors"])
    return result


def finish_run(run: ScrapeRun, *, status: str, complete: bool, stats: dict, errors: list[str], force: bool = False) -> dict:
    with transaction.atomic():
        run = ScrapeRun.objects.select_for_update().select_related("source").get(pk=run.pk)
        if run.status != ScrapeRun.Status.RUNNING:
            if run.finished_at and run.status != ScrapeRun.Status.ABANDONED:
                return summarize(run)  # a retried finish: answer the same way again
            raise RunClosed(f"run {run.pk} is {run.status}")

        now = timezone.now()
        open_jobs = Job.objects.filter(source=run.source, closed_at__isnull=True)
        stale = open_jobs.exclude(last_seen_run=run)
        closed, note = 0, ""
        if not complete or status == ScrapeRun.Status.FAILED:
            note = "listing incomplete: nothing was closed"
        else:
            open_count, stale_count = open_jobs.count(), stale.count()
            if stale_count and not force and stale_count > open_count * settings.MAX_CLOSE_FRACTION:
                note = (
                    f"refused to close {stale_count} of {open_count} open jobs "
                    f"(more than MAX_CLOSE_FRACTION={settings.MAX_CLOSE_FRACTION:g}); check the scraper"
                )
                log.warning("run %s: %s", run.pk, note)
            elif stale_count:
                fingerprints = set(stale.values_list("fingerprint", flat=True))
                closed = stale.update(closed_at=now, duplicate_of=None)
                regroup(fingerprints)

        run.status = status
        run.complete = complete
        run.finished_at = now
        run.scraper_stats = stats
        run.errors = (run.errors + list(errors))[:100]
        run.ingest_stats = {**run.ingest_stats, "closed": closed}
        run.note = note[:300]
        run.save()
    return summarize(run)


def summarize(run: ScrapeRun) -> dict:
    return {
        "id": run.pk,
        "source": run.source.slug,
        "status": run.status,
        "complete": run.complete,
        "closed": run.ingest_stats.get("closed", 0),
        "ingest": run.ingest_stats,
        "note": run.note,
    }


SALARY_TOLERANCE = 0.15


def match_score(a: Job, b: Job) -> int | None:
    """How well two same-fingerprint postings agree; None means they can't be one job.

    The fingerprint only says "same company, title and place". A company can
    have two remote "Frontend Engineer" openings, one worldwide and full-time,
    one US-only on contract. Fields both postings state must not contradict.
    """
    score = 0
    if a.remote_region and b.remote_region:
        if a.remote_region.lower() != b.remote_region.lower():
            return None
        score += 1
    if a.employment_type and b.employment_type:
        if a.employment_type != b.employment_type:
            return None
        score += 1
    if a.salary_usd_min and b.salary_usd_min:
        a_max, b_max = a.salary_usd_max or a.salary_usd_min, b.salary_usd_max or b.salary_usd_min
        slack = 1 + SALARY_TOLERANCE
        if a.salary_usd_min > b_max * slack or b.salary_usd_min > a_max * slack:
            return None
        score += 1
    return score


def cluster(jobs: list[Job]) -> list[list[Job]]:
    """Split one fingerprint's open postings into jobs. The first of each cluster is canonical.

    Postings are taken salary-first (more useful to show), then oldest first.
    Each joins the best-matching cluster that has nothing from its own board yet:
    a board listing the same title twice means two openings, not a duplicate.
    """
    clusters: list[list[Job]] = []
    for job in sorted(jobs, key=lambda j: (j.salary_min is None, j.first_seen_at, j.pk)):
        best, best_score = None, -1
        for candidate in clusters:
            if any(member.source_id == job.source_id for member in candidate):
                continue
            score = match_score(candidate[0], job)
            if score is not None and score > best_score:
                best, best_score = candidate, score
        if best is None:
            clusters.append([job])
        else:
            best.append(job)
    return clusters


def regroup(fingerprints) -> int:
    """Recompute the duplicate links for these fingerprints; returns how many changed."""
    fingerprints = {fp for fp in fingerprints if fp}
    if not fingerprints:
        return 0
    changed: list[Job] = []
    jobs = Job.objects.filter(fingerprint__in=fingerprints).only(
        "id", "fingerprint", "source_id", "closed_at", "duplicate_of_id", "salary_min", "first_seen_at",
        "remote_region", "employment_type", "salary_usd_min", "salary_usd_max",
    )
    groups: dict[str, list[Job]] = {}
    for job in jobs:
        groups.setdefault(job.fingerprint, []).append(job)
    for group in groups.values():
        target_of: dict[int, int | None] = {}
        for members in cluster([j for j in group if j.closed_at is None]):
            for member in members[1:]:
                target_of[member.pk] = members[0].pk
        for job in group:
            target = target_of.get(job.pk)
            if job.duplicate_of_id != target:
                job.duplicate_of_id = target
                changed.append(job)
    # Jobs elsewhere that still point at a job which is now a duplicate or closed.
    if changed:
        Job.objects.bulk_update(changed, ["duplicate_of"])
    dangling = Job.objects.filter(Q(duplicate_of__duplicate_of__isnull=False) | Q(duplicate_of__closed_at__isnull=False))
    extra = set(dangling.values_list("fingerprint", flat=True)) - fingerprints
    return len(changed) + (regroup(extra) if extra else 0)


def close_stale(days: int) -> int:
    """Safety net for sources whose runs are never complete: close jobs unseen for `days`."""
    cutoff = timezone.now() - timedelta(days=days)
    with transaction.atomic():
        stale = Job.objects.filter(closed_at__isnull=True, last_seen_at__lt=cutoff)
        fingerprints = set(stale.values_list("fingerprint", flat=True))
        count = stale.update(closed_at=timezone.now(), duplicate_of=None)
        regroup(fingerprints)
    return count

def revoke_access(data=None):
    if data is None:
        return None
    return data