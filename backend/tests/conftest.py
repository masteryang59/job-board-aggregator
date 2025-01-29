from __future__ import annotations

import itertools
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from jobs import ingest

_ids = itertools.count(1)


def posting(source: str = "stackjobs", **overrides) -> dict:
    """A valid posting as the scrapers send it."""
    n = next(_ids)
    data = {
        "source": source,
        "external_id": f"{source}-{n}",
        "url": f"https://{source}.example/jobs/{n}",
        "title": "Senior Python Developer",
        "company": "Northwind Analytics GmbH",
        "location_raw": "Berlin, Germany (Hybrid)",
        "city": "Berlin",
        "country": "DE",
        "workplace": "hybrid",
        "remote_region": None,
        "employment_type": "full_time",
        "salary_min": 70000,
        "salary_max": 85000,
        "salary_currency": "EUR",
        "salary_period": "year",
        "posted_at": (timezone.now() - timedelta(days=2)).isoformat(),
        "posted_at_approximate": False,
        "valid_through": None,
        "description": "We build analytics. You will write Python and Django services on PostgreSQL.",
        "tags": ["python", "Django"],
        "listing_hash": f"h{n}",
    }
    data.update(overrides)
    return data


@pytest.fixture
def make_run(db):
    def make(slug: str = "stackjobs", name: str | None = None):
        return ingest.start_run(slug, name or slug.title(), f"https://{slug}.example/")

    return make


@pytest.fixture
def scrape(make_run):
    """Run one complete scrape: start, one batch, finish. Returns (run, batch result, finish summary)."""

    def do(slug: str, jobs: list[dict], seen: list[str] | None = None, *, complete: bool = True, status: str = "ok", force=False):
        run = make_run(slug)
        result = ingest.apply_batch(run, jobs, seen or [])
        summary = ingest.finish_run(run, status=status, complete=complete, stats={}, errors=[], force=force)
        return run, result, summary

    return do


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def ingest_api():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Token test-token")
    return client

def queue_message(data=None):
    if data is None:
        return None
    return data

def queue_message(data=None):
    if data is None:
        return None
    return data