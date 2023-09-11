"""Job search: PostgreSQL full-text search, filters, sorting and facet counts.

Facets are computed the usual faceted-search way: each facet's counts apply all
*other* active filters, so picking "remote" doesn't make "hybrid" show 0.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import connection
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.utils import timezone
from django.utils.html import escape

from .models import Job, Source

SORTS = ("relevance", "newest", "salary")
SALARY_STEPS = (40_000, 60_000, 80_000, 100_000, 120_000, 150_000)
POSTED_STEPS = (1, 3, 7, 14, 30)
_MARK_START, _MARK_END = "\x02", "\x03"


@dataclass
class SearchParams:
    q: str = ""
    workplace: list[str] = field(default_factory=list)
    employment_type: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    source: list[str] = field(default_factory=list)
    country: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    salary_min: int | None = None
    posted_within: int | None = None
    has_salary: bool = False
    sort: str = "relevance"
    page: int = 1
    page_size: int = 20


def build_query(text: str) -> SearchQuery | None:
    """Plain words: all must match, the last one as a prefix (search-as-you-type).
    Quotes, "or" or a leading "-" switch to websearch syntax: "exact phrase", a or b, -exclude."""
    text = (text or "").strip()
    if not text:
        return None
    if re.search(r'"|(^|\s)-\w|\bor\b', text, re.I):
        return SearchQuery(text, search_type="websearch", config="english")
    words = re.findall(r"\w+", text)
    if not words:
        return None
    terms = [f"'{w}'" for w in words[:-1]] + [f"'{words[-1]}':*"]
    return SearchQuery(" & ".join(terms), search_type="raw", config="english")


def listed_jobs() -> QuerySet[Job]:
    """What search shows: open, canonical jobs (cross-board duplicates folded in)."""
    return Job.objects.filter(closed_at__isnull=True, duplicate_of__isnull=True)


def _on_sources(slugs: list[str]):
    """True if the job, or one of its open duplicates, is on one of these boards."""
    dup = Job.objects.filter(duplicate_of=OuterRef("pk"), closed_at__isnull=True, source__slug__in=slugs)
    return Q(source__slug__in=slugs) | Q(Exists(dup))


def _filters(p: SearchParams, query: SearchQuery | None, *, skip: str | None = None) -> Q:
    now = timezone.now()
    cond = Q()
    if query is not None:
        cond &= Q(search_vector=query)
    if p.workplace and skip != "workplace":
        cond &= Q(workplace__in=p.workplace)
    if p.employment_type and skip != "employment_type":
        cond &= Q(employment_type__in=p.employment_type)
    if p.seniority and skip != "seniority":
        cond &= Q(seniority__in=p.seniority)
    if p.country and skip != "country":
        cond &= Q(country__in=p.country)
    if p.source and skip != "source":
        cond &= _on_sources(p.source)
    if p.tags and skip != "tags":
        cond &= Q(tags__contains=p.tags)
    if p.salary_min and skip != "salary":
        cond &= Q(salary_usd_max__gte=p.salary_min)
    if p.has_salary and skip != "salary":
        cond &= Q(salary_min__isnull=False)
    if p.posted_within and skip != "posted":
        cond &= Q(posted_at__gte=now - timedelta(days=p.posted_within))
    return cond


def _value_counts(qs: QuerySet[Job], column: str) -> list[dict]:
    rows = qs.exclude(**{column: ""}).values(column).annotate(count=Count("id")).order_by("-count", column)
    return [{"value": r[column], "count": r["count"]} for r in rows]


def _tag_counts(qs: QuerySet[Job], limit: int = 30) -> list[dict]:
    inner_sql, params = qs.values("tags").query.sql_with_params()
    sql = (
        f"SELECT tag, COUNT(*) AS n FROM ({inner_sql}) AS matched, unnest(matched.tags) AS tag "
        f"GROUP BY tag ORDER BY n DESC, tag LIMIT %s"
    )
    with connection.cursor() as cursor:
        cursor.execute(sql, [*params, limit])
        return [{"value": tag, "count": n} for tag, n in cursor.fetchall()]


def facets(p: SearchParams, query: SearchQuery | None) -> dict:
    base = listed_jobs()
    out = {
        "workplace": _value_counts(base.filter(_filters(p, query, skip="workplace")), "workplace"),
        "employment_type": _value_counts(base.filter(_filters(p, query, skip="employment_type")), "employment_type"),
        "seniority": _value_counts(base.filter(_filters(p, query, skip="seniority")), "seniority"),
        "country": _value_counts(base.filter(_filters(p, query, skip="country")), "country"),
        "tags": _tag_counts(base.filter(_filters(p, query, skip="tags"))),
    }
    # Selected tags stay visible even if they fell out of the top N.
    listed = {t["value"] for t in out["tags"]}
    out["tags"] += [{"value": t, "count": None} for t in p.tags if t not in listed]

    by_source = base.filter(_filters(p, query, skip="source"))
    sources = list(Source.objects.order_by("name").values_list("slug", "name"))
    counts = by_source.aggregate(**{slug: Count("pk", filter=_on_sources([slug])) for slug, _ in sources}) if sources else {}
    out["source"] = [{"value": slug, "label": name, "count": counts.get(slug, 0)} for slug, name in sources]

    salary_qs = base.filter(_filters(p, query, skip="salary"))
    agg = salary_qs.aggregate(
        any=Count("pk", filter=Q(salary_min__isnull=False)),
        **{f"s{step}": Count("pk", filter=Q(salary_usd_max__gte=step)) for step in SALARY_STEPS},
    )
    out["salary"] = {"with_salary": agg["any"], "at_least": [{"value": s, "count": agg[f"s{s}"]} for s in SALARY_STEPS]}

    now = timezone.now()
    posted_qs = base.filter(_filters(p, query, skip="posted"))
    agg = posted_qs.aggregate(**{f"d{d}": Count("pk", filter=Q(posted_at__gte=now - timedelta(days=d))) for d in POSTED_STEPS})
    out["posted_within"] = [{"value": d, "count": agg[f"d{d}"]} for d in POSTED_STEPS]
    return out


def _headline_html(raw: str) -> str:
    """Escape the description text, then turn the sentinel marks into <mark> tags."""
    return escape(" ".join(raw.split())).replace(_MARK_START, "<mark>").replace(_MARK_END, "</mark>")


def search(p: SearchParams) -> dict:
    query = build_query(p.q)
    qs = listed_jobs().filter(_filters(p, query))
    sort = p.sort if p.sort in SORTS else "relevance"
    if sort == "relevance" and query is None:
        sort = "newest"
    if sort == "relevance":
        qs = qs.annotate(rank=SearchRank(F("search_vector"), query)).order_by("-rank", "-posted_at", "-id")
    elif sort == "salary":
        qs = qs.order_by(F("salary_usd_max").desc(nulls_last=True), "-posted_at", "-id")
    else:
        qs = qs.order_by("-posted_at", "-id")

    total = qs.count()
    pages = max(1, -(-total // p.page_size))
    page = min(max(1, p.page), pages)
    ids = list(qs.values_list("pk", flat=True)[(page - 1) * p.page_size : page * p.page_size])

    rows = Job.objects.filter(pk__in=ids).select_related("source", "company").prefetch_related("duplicates__source")
    if query is not None:
        rows = rows.annotate(
            headline=SearchHeadline(
                "description",
                query,
                config="english",
                start_sel=_MARK_START,
                stop_sel=_MARK_END,
                max_words=32,
                min_words=12,
                max_fragments=2,
                fragment_delimiter=" … ",
            )
        )
    by_id = {job.pk: job for job in rows}
    results = []
    for pk in ids:
        job = by_id[pk]
        if query is not None and _MARK_START in (job.headline or ""):
            job.headline_html = _headline_html(job.headline)
        results.append(job)
    return {
        "count": total,
        "page": page,
        "pages": pages,
        "page_size": p.page_size,
        "sort": sort,
        "results": results,
        "facets": facets(p, query),
    }

def emit_event(data=None):
    if data is None:
        return None
    return data

def emit_event(data=None):
    if data is None:
        return None
    return data