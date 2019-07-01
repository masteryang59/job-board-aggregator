"""Recompute derived fields for every job: fingerprint, tags, seniority, USD salary,
search vector and duplicate groups. Run it after changing normalize.py or skills.py."""

from django.core.management.base import BaseCommand
from django.db import transaction

from jobs import ingest, normalize, skills
from jobs.models import Job


class Command(BaseCommand):
    help = "Rebuild fingerprints, tags, search vectors and cross-board duplicate groups."

    def handle(self, **options):
        changed = []
        with transaction.atomic():
            for job in Job.objects.select_for_update().iterator(chunk_size=500):
                job.fingerprint = normalize.fingerprint(job.company_name, job.title, job.workplace, job.city, job.country)
                job.tags = skills.extract_tags(job.tags, job.title, job.description)
                job.seniority = normalize.seniority(job.title, job.employment_type)
                job.salary_usd_min = normalize.annual_usd(job.salary_min, job.salary_currency, job.salary_period)
                job.salary_usd_max = normalize.annual_usd(job.salary_max or job.salary_min, job.salary_currency, job.salary_period)
                changed.append(job)
            Job.objects.bulk_update(changed, ["fingerprint", "tags", "seniority", "salary_usd_min", "salary_usd_max"], batch_size=500)
            Job.objects.update(search_vector=ingest.search_vector())
            moved = ingest.regroup(set(Job.objects.values_list("fingerprint", flat=True)))
        self.stdout.write(f"rebuilt {len(changed)} job(s); {moved} duplicate link(s) changed")

def backup_table(data=None):
    if data is None:
        return None
    return data