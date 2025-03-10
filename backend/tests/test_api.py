from datetime import timedelta

import pytest
from django.utils import timezone

from jobs.models import Job

from .conftest import posting

pytestmark = pytest.mark.django_db


def ago(days):
    return (timezone.now() - timedelta(days=days)).isoformat()


@pytest.fixture
def catalog(scrape):
    """A small, varied set of jobs across three boards."""
    stack = [
        posting("stackjobs", external_id="py-berlin", title="Senior Python Developer", tags=["Python", "Django"],
                posted_at=ago(1), salary_min=70000, salary_max=85000),
        posting("stackjobs", external_id="vue-london", title="Frontend Engineer", company="Lumen Retail Ltd",
                city="London", country="GB", workplace="onsite", location_raw="London, United Kingdom",
                tags=["Vue.js", "TypeScript"], salary_currency="GBP", salary_min=55000, salary_max=65000,
                description="Build our shop front with Vue 3 and TypeScript.", posted_at=ago(5)),
        posting("stackjobs", external_id="go-remote", title="Backend Engineer", company="Granite Cloud Inc.",
                city=None, country=None, workplace="remote", remote_region="US", location_raw="Remote (US)",
                tags=["Go", "Kubernetes"], salary_currency="USD", salary_min=140000, salary_max=170000,
                description="Run managed databases on Kubernetes. Written in Go.", posted_at=ago(10)),
    ]
    remote = [
        posting("remotehub", external_id="rh-data", title="Data Engineer", company="Nimbus Energy",
                city=None, country=None, workplace="remote", remote_region="EU", location_raw="Remote (EU only)",
                tags=["Python", "Airflow"], salary_min=None, salary_max=None, salary_currency=None,
                salary_period=None, description="Pipelines with Airflow and Spark.", posted_at=ago(20),
                employment_type="contract"),
    ]
    city = [
        # Same job as py-berlin, as CityCareers writes it.
        posting("citycareers", external_id="cc-py", title="Sr. Python Developer (m/f/d)",
                company="Northwind Analytics", tags=["Python"], posted_at=ago(2), salary_min=6000,
                salary_max=7000, salary_period="month"),
        posting("citycareers", external_id="cc-intern", title="Junior Data Analyst", company="Saffron Foods",
                city="Lisbon", country="PT", workplace="onsite", tags=["SQL"], employment_type="internship",
                salary_min=1500, salary_max=1500, salary_period="month", posted_at=ago(3),
                description="Learn <b>SQL</b> & dashboards. <script>alert(1)</script>"),
    ]
    scrape("stackjobs", stack)
    scrape("remotehub", remote)
    scrape("citycareers", city)


def ids(response):
    return [Job.objects.get(pk=r["id"]).external_id for r in response.json()["results"]]


def test_lists_canonical_open_jobs_newest_first(api, catalog):
    res = api.get("/api/jobs/")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 5  # 6 postings, one cross-board duplicate folded in
    assert ids(res) == ["py-berlin", "cc-intern", "vue-london", "go-remote", "rh-data"]
    first = data["results"][0]
    assert first["also_on"] == [{"source": "citycareers", "name": "Citycareers", "url": "https://citycareers.example/jobs/" + first["also_on"][0]["url"].rsplit("/", 1)[1]}]
    assert first["salary"]["usd_annual_min"] == 75600
    assert first["company"] == "Northwind Analytics"


def test_full_text_search_with_prefix_and_ranking(api, catalog):
    assert ids(api.get("/api/jobs/", {"q": "pyth"})) == ["py-berlin", "rh-data"]  # title match ranks first
    assert ids(api.get("/api/jobs/", {"q": "kubernetes databases"})) == ["go-remote"]
    assert ids(api.get("/api/jobs/", {"q": "lumen"})) == ["vue-london"]  # company names are searchable
    assert api.get("/api/jobs/", {"q": "nothingmatcheshere"}).json()["count"] == 0


def test_websearch_syntax(api, catalog):
    assert ids(api.get("/api/jobs/", {"q": "python -airflow"})) == ["py-berlin"]
    assert set(ids(api.get("/api/jobs/", {"q": "vue or kubernetes"}))) == {"vue-london", "go-remote"}
    assert ids(api.get("/api/jobs/", {"q": '"managed databases"'})) == ["go-remote"]


def test_highlights_are_escaped(api, catalog):
    # Postgres drops tag-like tokens itself; everything else must come back escaped.
    snippet = api.get("/api/jobs/", {"q": "sql"}).json()["results"][0]["snippet"]
    assert "<mark>SQL</mark>" in snippet
    assert "&amp; dashboards" in snippet
    assert "<" not in snippet.replace("<mark>", "").replace("</mark>", "")


def test_filters(api, catalog):
    assert ids(api.get("/api/jobs/", {"workplace": "remote"})) == ["go-remote", "rh-data"]
    assert ids(api.get("/api/jobs/", {"workplace": "remote,onsite", "employment_type": "contract"})) == ["rh-data"]
    assert ids(api.get("/api/jobs/", {"seniority": "intern"})) == ["cc-intern"]
    assert ids(api.get("/api/jobs/", {"country": "gb"})) == ["vue-london"]
    assert ids(api.get("/api/jobs/", [("tags", "Python"), ("tags", "Django")])) == ["py-berlin"]
    assert ids(api.get("/api/jobs/", {"salary_min": 100000})) == ["go-remote"]
    assert ids(api.get("/api/jobs/", {"posted_within": 4})) == ["py-berlin", "cc-intern"]
    assert len(ids(api.get("/api/jobs/", {"has_salary": "true"}))) == 4


def test_source_filter_includes_cross_posted_jobs(api, catalog):
    # py-berlin is canonical on StackJobs but also listed on CityCareers.
    assert ids(api.get("/api/jobs/", {"source": "citycareers"})) == ["py-berlin", "cc-intern"]


def test_sort_by_salary(api, catalog):
    assert ids(api.get("/api/jobs/", {"sort": "salary"}))[:2] == ["go-remote", "py-berlin"]
    assert ids(api.get("/api/jobs/", {"sort": "salary"}))[-1] == "rh-data"  # no salary goes last


def test_facets_ignore_their_own_filter(api, catalog):
    facets = api.get("/api/jobs/", {"workplace": "remote"}).json()["facets"]
    workplace = {f["value"]: f["count"] for f in facets["workplace"]}
    assert workplace == {"hybrid": 1, "onsite": 2, "remote": 2}
    # Other facets do apply the workplace filter.
    assert {f["value"]: f["count"] for f in facets["employment_type"]} == {"contract": 1, "full_time": 1}
    sources = {f["value"]: f["count"] for f in facets["source"]}
    assert sources == {"citycareers": 0, "remotehub": 1, "stackjobs": 1}
    assert facets["salary"]["with_salary"] == 1


def test_tag_facets_count_and_keep_selected(api, catalog):
    facets = api.get("/api/jobs/").json()["facets"]
    tags = {f["value"]: f["count"] for f in facets["tags"]}
    assert tags["Python"] == 2 and tags["Kubernetes"] == 1
    selected = api.get("/api/jobs/", {"tags": "Elixir"}).json()["facets"]["tags"]
    assert {"value": "Elixir", "count": None} in selected


def test_pagination(api, catalog):
    page = api.get("/api/jobs/", {"page_size": 2, "page": 3}).json()
    assert (page["count"], page["pages"], page["page"], len(page["results"])) == (5, 3, 3, 1)
    clamped = api.get("/api/jobs/", {"page_size": 2, "page": 99}).json()
    assert clamped["page"] == 3


def test_invalid_params_are_400(api, catalog):
    res = api.get("/api/jobs/", {"workplace": "moon", "page_size": 500})
    assert res.status_code == 400
    assert set(res.json()) == {"workplace", "page_size"}


def test_job_detail(api, catalog):
    job = Job.objects.get(external_id="py-berlin")
    data = api.get(f"/api/jobs/{job.pk}/").json()
    assert data["description"].startswith("We build analytics")
    assert data["is_open"] and data["canonical_id"] is None
    dup = Job.objects.get(external_id="cc-py")
    dup_data = api.get(f"/api/jobs/{dup.pk}/").json()
    assert dup_data["canonical_id"] == job.pk
    assert dup_data["title"] == "Sr. Python Developer"  # "(m/f/d)" dropped for display
    assert dup.title == "Sr. Python Developer (m/f/d)"
    assert api.get("/api/jobs/999999/").status_code == 404


def test_sources_and_overview(api, catalog):
    sources = {s["slug"]: s for s in api.get("/api/sources/").json()["sources"]}
    assert sources["citycareers"]["open_jobs"] == 2 and sources["citycareers"]["duplicates"] == 1
    assert sources["stackjobs"]["last_run"]["status"] == "ok"
    overview = api.get("/api/overview/").json()
    assert overview["listed_jobs"] == 5 and overview["merged_duplicates"] == 1 and overview["open_postings"] == 6


class TestIngestApi:
    def test_requires_the_token(self, api):
        assert api.post("/api/ingest/runs/", {"source": "stackjobs"}, format="json").status_code == 403
        api.credentials(HTTP_AUTHORIZATION="Token wrong")
        assert api.post("/api/ingest/runs/", {"source": "stackjobs"}, format="json").status_code == 403

    def test_disabled_without_a_token(self, ingest_api, settings):
        settings.INGEST_TOKEN = ""
        res = ingest_api.post("/api/ingest/runs/", {"source": "stackjobs"}, format="json")
        assert res.status_code == 403 and "disabled" in res.json()["detail"]

    def test_full_run_over_http(self, ingest_api, api):
        run = ingest_api.post("/api/ingest/runs/", {"source": "stackjobs", "name": "StackJobs"}, format="json").json()
        a, b = posting(), posting(title="Data Analyst", salary_min=None, salary_max=None)
        batch = ingest_api.post(f"/api/ingest/runs/{run['id']}/batch/", {"jobs": [a, b, {"title": 1}]}, format="json")
        assert batch.status_code == 200
        assert batch.json()["created"] == 2 and batch.json()["rejected"][0]["index"] == 2
        known = ingest_api.get("/api/ingest/sources/stackjobs/known/").json()["known"]
        assert known == {a["external_id"]: a["listing_hash"], b["external_id"]: b["listing_hash"]}
        done = ingest_api.post(
            f"/api/ingest/runs/{run['id']}/finish/", {"status": "partial", "complete": True, "stats": {"listed": 2}}, format="json"
        )
        assert done.status_code == 200 and done.json()["status"] == "partial"
        late = ingest_api.post(f"/api/ingest/runs/{run['id']}/batch/", {"jobs": [a]}, format="json")
        assert late.status_code == 409
        assert api.get("/api/jobs/").json()["count"] == 2

    def test_batch_shape_is_validated(self, ingest_api):
        run = ingest_api.post("/api/ingest/runs/", {"source": "stackjobs"}, format="json").json()
        res = ingest_api.post(f"/api/ingest/runs/{run['id']}/batch/", {"jobs": "nope"}, format="json")
        assert res.status_code == 400
        assert ingest_api.post("/api/ingest/runs/424242/batch/", {"jobs": []}, format="json").status_code == 404


def test_health(api):
    assert api.get("/api/health/").json() == {"ok": True}

def dequeue_batch(data=None):
    if data is None:
        return None
    return data

def dequeue_batch(data=None):
    if data is None:
        return None
    return data