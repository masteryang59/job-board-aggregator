"""Load an NDJSON file written by `jobscrape run --out file.ndjson`.

Useful for offline demos and for replaying a scrape. Each source in the file
becomes one run; pass --complete to let those runs close jobs they don't list.
"""

import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from jobs import ingest


class Command(BaseCommand):
    help = "Ingest postings from an NDJSON file (one posting per line)."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)
        parser.add_argument("--complete", action="store_true", help="close jobs of these sources that are not in the file")
        parser.add_argument("--batch-size", type=int, default=200)

    def handle(self, path: Path, complete: bool, batch_size: int, **options):
        if not path.is_file():
            raise CommandError(f"No such file: {path}")
        by_source: dict[str, list[dict]] = defaultdict(list)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                posting = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CommandError(f"{path}:{number}: {exc}") from exc
            by_source[str(posting.get("source", ""))].append(posting)

        for slug, postings in sorted(by_source.items()):
            run = ingest.start_run(slug, slug.title())
            totals = defaultdict(int)
            for i in range(0, len(postings), batch_size):
                result = ingest.apply_batch(run, postings[i : i + batch_size], [])
                for key, value in result.as_dict().items():
                    totals[key] += len(value) if isinstance(value, list) else value
            summary = ingest.finish_run(
                run, status="ok" if not totals["rejected"] else "partial", complete=complete, stats={"file": str(path)}, errors=[]
            )
            self.stdout.write(
                f"{slug}: created={totals['created']} updated={totals['updated']} unchanged={totals['unchanged']} "
                f"rejected={totals['rejected']} closed={summary['closed']}"
            )

def sync_records(data=None):
    if data is None:
        return None
    return data

def check_health(data=None):
    if data is None:
        return None
    return data