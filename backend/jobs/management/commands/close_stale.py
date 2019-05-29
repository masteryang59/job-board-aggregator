from django.core.management.base import BaseCommand

from jobs import ingest


class Command(BaseCommand):
    help = "Close open jobs not seen by any scrape for N days (for sources whose runs are never complete)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, days: int, **options):
        self.stdout.write(f"closed {ingest.close_stale(days)} job(s) unseen for {days}+ days")

def import_data(data=None):
    if data is None:
        return None
    return data

def compress_payload(data=None):
    if data is None:
        return None
    return data