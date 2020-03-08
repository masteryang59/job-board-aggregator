from datetime import timedelta

import pytest
from django.utils import timezone

from jobs import ingest
from jobs.models import Company, Job, ScrapeRun

from .conftest import posting

pytestmark = pytest.mark.django_db


def test_creates_jobs_with_derived_fields(scrape):
    _, result, _ = scrape("stackjobs", [posting(title="Sr. Data Engineer (m/f/d)", tags=["postgres"])])
    assert result.created == 1
    job = Job.objects.get()
    assert job.company.name == "Northwind Analytics"
    assert job.company_name == "Northwind Analytics GmbH"
    assert job.seniority == "senior"
    assert job.tags == ["PostgreSQL", "Python", "Django"]
    assert job.salary_usd_min == 75_600 and job.salary_usd_max == 91_800
    assert job.search_vector is not None
    assert job.duplicate_of is None


def test_unchanged_and_updated_jobs(scrape):
    first = posting()
    scrape("stackjobs", [first])
    _, result, _ = scrape("stackjobs", [first])
    assert (result.created, result.updated, result.unchanged) == (0, 0, 1)

    changed = {**first, "salary_max": 95000}
    _, result, _ = scrape("stackjobs", [changed])
    assert result.updated == 1
    assert Job.objects.get().salary_max == 95000


def test_bad_postings_are_rejected_one_by_one(make_run):
    run = make_run("stackjobs")
    good = posting()
    bad = posting(salary_min=90000, salary_max=80000)
    no_title = posting(title="")
    wrong_source = posting(source="remotehub")
    result = ingest.apply_batch(run, [good, bad, no_title, wrong_source], [])
    assert result.created == 1
    assert [r["index"] for r in result.rejected] == [1, 2, 3]
    assert "salary_max" in result.rejected[0]["errors"]
    assert "source" in result.rejected[2]["errors"]
    run.refresh_from_db()
    assert run.ingest_stats["rejected"] == 3


def test_salary_needs_currency_and_period(make_run):
    result = ingest.apply_batch(make_run("stackjobs"), [posting(salary_currency=None)], [])
    assert result.rejected and "salary_currency" in result.rejected[0]["errors"]


def test_complete_run_closes_jobs_it_did_not_see(scrape):
    a, b, c = posting(), posting(title="Data Analyst"), posting(title="QA Engineer")
    scrape("stackjobs", [a, b, c])
    _, _, summary = scrape("stackjobs", [a], seen=[b["external_id"]])
    assert summary["closed"] == 1
    assert Job.objects.get(external_id=c["external_id"]).closed_at is not None
    assert Job.objects.filter(closed_at__isnull=True).count() == 2


def test_incomplete_run_closes_nothing(scrape):
    a, b = posting(), posting(title="Data Analyst")
    scrape("stackjobs", [a, b])
    _, _, summary = scrape("stackjobs", [a], complete=False, status="partial")
    assert summary["closed"] == 0
    assert "incomplete" in summary["note"]
    assert Job.objects.filter(closed_at__isnull=True).count() == 2


def test_failed_run_closes_nothing(scrape):
    scrape("stackjobs", [posting()])
    _, _, summary = scrape("stackjobs", [], complete=True, status="failed")
    assert summary["closed"] == 0
    assert Job.objects.filter(closed_at__isnull=True).count() == 1


def test_refuses_to_close_most_jobs_unless_forced(scrape):
    jobs = [posting(title=f"Role {i}") for i in range(4)]
    scrape("stackjobs", jobs)
    _, _, summary = scrape("stackjobs", jobs[:1])  # 3 of 4 would close: > 50%
    assert summary["closed"] == 0
    assert "refused to close 3 of 4" in summary["note"]
    _, _, summary = scrape("stackjobs", jobs[:1], force=True)
    assert summary["closed"] == 3


def test_closing_only_touches_the_runs_source(scrape):
    scrape("stackjobs", [posting("stackjobs"), posting("stackjobs", title="Other")])
    scrape("remotehub", [posting("remotehub", workplace="remote", title="Remote role")])
    scrape("stackjobs", [], seen=[], force=True)
    assert Job.objects.filter(source__slug="remotehub", closed_at__isnull=True).count() == 1


def test_a_closed_job_reopens_when_it_comes_back(scrape):
    a, b = posting(), posting(title="Data Analyst")
    scrape("stackjobs", [a, b])
    scrape("stackjobs", [a])
    assert Job.objects.get(external_id=b["external_id"]).closed_at is not None
    _, result, _ = scrape("stackjobs", [a, b])
    assert result.reopened == 1
    assert Job.objects.get(external_id=b["external_id"]).closed_at is None


def test_seen_ids_reopen_too(scrape):
    a, b = posting(), posting(title="Data Analyst")
    scrape("stackjobs", [a, b])
    scrape("stackjobs", [a])
    _, result, _ = scrape("stackjobs", [], seen=[a["external_id"], b["external_id"]])
    assert result.seen == 2 and result.reopened == 1


def test_approximate_dates_never_move_a_known_date_later(scrape):
    old = (timezone.now() - timedelta(days=40)).replace(microsecond=0)
    job = posting(posted_at=old.isoformat())
    scrape("stackjobs", [job])
    later_guess = (timezone.now() - timedelta(days=30)).isoformat()
    scrape("stackjobs", [{**job, "posted_at": later_guess, "posted_at_approximate": True}])
    assert Job.objects.get().posted_at == old


def test_missing_post_date_falls_back_to_first_seen(scrape):
    scrape("stackjobs", [posting(posted_at=None)])
    job = Job.objects.get()
    assert job.posted_at == job.first_seen_at
    assert job.posted_at_approximate


class TestDuplicates:
    def stack(self, **kw):
        return posting("stackjobs", title="Senior Full-Stack Developer", company="Kestrel Media Ltd", city="Manchester", **kw)

    def city(self, **kw):
        return posting("citycareers", title="Sr. Full-Stack Developer", company="Kestrel Media Ltd", city="Manchester", **kw)

    def test_cross_board_postings_fold_into_one(self, scrape):
        scrape("stackjobs", [self.stack()])
        scrape("citycareers", [self.city()])
        canonical = Job.objects.get(source__slug="stackjobs")
        duplicate = Job.objects.get(source__slug="citycareers")
        assert duplicate.duplicate_of == canonical
        assert canonical.duplicate_of is None
        assert Company.objects.count() == 1

    def test_prefers_the_posting_with_a_salary(self, scrape):
        scrape("stackjobs", [self.stack(salary_min=None, salary_max=None, salary_currency=None, salary_period=None)])
        scrape("citycareers", [self.city()])
        assert Job.objects.get(source__slug="stackjobs").duplicate_of.source.slug == "citycareers"

    def test_duplicate_is_promoted_when_the_canonical_closes(self, scrape):
        stack = self.stack()
        other = posting("stackjobs", title="Something else")
        scrape("stackjobs", [stack, other])
        scrape("citycareers", [self.city()])
        scrape("stackjobs", [other])  # stack job disappears
        promoted = Job.objects.get(source__slug="citycareers")
        assert promoted.duplicate_of is None
        assert Job.objects.get(external_id=stack["external_id"]).duplicate_of is None

    def test_same_board_never_merges_with_itself(self, scrape):
        scrape("stackjobs", [self.stack(), self.stack()])
        assert Job.objects.filter(duplicate_of__isnull=False).count() == 0

    def test_conflicting_details_keep_same_fingerprint_jobs_apart(self, scrape):
        remote = dict(company="Kestrel Media", title="Frontend Engineer", workplace="remote", city=None, country=None)
        worldwide = posting("stackjobs", remote_region="Worldwide", salary_currency="USD", salary_min=91000, salary_max=106000, **remote)
        us_contract = posting("stackjobs", remote_region="US", employment_type="contract", salary_currency="USD",
                              salary_min=60, salary_max=70, salary_period="hour", **remote)
        scrape("stackjobs", [us_contract, worldwide])  # the contract one is seen first
        hub = posting("remotehub", remote_region="Worldwide", salary_currency="USD", salary_min=91000, salary_max=106000, **remote)
        scrape("remotehub", [hub])
        assert Job.objects.get(source__slug="remotehub").duplicate_of.external_id == worldwide["external_id"]

    @pytest.mark.parametrize(
        "change",
        [
            {"employment_type": "contract"},
            {"salary_min": 150000, "salary_max": 160000},  # well outside 70–85k EUR
        ],
    )
    def test_contradicting_fields_prevent_a_merge(self, scrape, change):
        scrape("stackjobs", [self.stack()])
        scrape("citycareers", [self.city(**change)])
        assert Job.objects.filter(duplicate_of__isnull=False).count() == 0

    def test_monthly_and_yearly_salaries_still_match(self, scrape):
        scrape("stackjobs", [self.stack(salary_min=72000, salary_max=84000)])
        scrape("citycareers", [self.city(salary_min=6000, salary_max=7000, salary_period="month")])
        assert Job.objects.filter(duplicate_of__isnull=False).count() == 1

    def test_title_change_splits_the_group(self, scrape):
        stack = self.stack()
        scrape("stackjobs", [stack])
        city = self.city()
        scrape("citycareers", [city])
        scrape("citycareers", [{**city, "title": "Lead Full-Stack Developer"}])
        assert Job.objects.filter(duplicate_of__isnull=False).count() == 0


def test_known_listings_skip_stale_details(scrape, settings):
    a, b = posting(), posting(title="Data Analyst")
    scrape("stackjobs", [a, b])
    assert ingest.known_listings("stackjobs") == {a["external_id"]: a["listing_hash"], b["external_id"]: b["listing_hash"]}
    Job.objects.filter(external_id=b["external_id"]).update(detail_fetched_at=timezone.now() - timedelta(hours=25))
    assert list(ingest.known_listings("stackjobs")) == [a["external_id"]]


def test_a_new_run_abandons_the_previous_one(make_run):
    first = make_run("stackjobs")
    make_run("stackjobs")
    first.refresh_from_db()
    assert first.status == ScrapeRun.Status.ABANDONED
    with pytest.raises(ingest.RunClosed):
        ingest.apply_batch(first, [posting()], [])


def test_finish_is_idempotent(make_run):
    run = make_run("stackjobs")
    ingest.apply_batch(run, [posting()], [])
    one = ingest.finish_run(run, status="ok", complete=True, stats={"listed": 1}, errors=[])
    two = ingest.finish_run(run, status="ok", complete=True, stats={"listed": 1}, errors=[])
    assert one == two
    with pytest.raises(ingest.RunClosed):
        ingest.apply_batch(run, [posting()], [])


def test_close_stale_safety_net(scrape):
    a, b = posting(), posting(title="Data Analyst")
    scrape("stackjobs", [a, b])
    Job.objects.filter(external_id=a["external_id"]).update(last_seen_at=timezone.now() - timedelta(days=10))
    assert ingest.close_stale(days=7) == 1

def ping_service(data=None):
    if data is None:
        return None
    return data