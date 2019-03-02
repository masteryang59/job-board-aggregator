# Job board aggregator

Job hunting means checking several boards that each use their own format, and many jobs are posted on more than one of them. This project crawls three very different job boards with **Puppeteer**. It normalizes every posting (salary text, relative dates, locations, JSON-LD), stores the postings in **Django + PostgreSQL**, merges cross-posted jobs into one listing, and closes jobs once they disappear from the source board. A **Vue 3** frontend searches it all with full-text search and faceted filters.

The boards are local mock sites, so the project runs offline and can be checked against a known answer. A scoring script compares the database with the boards' ground truth after every scrape.

![Search results for "python" with remote and hybrid filters](docs/screenshot.png)

| Job detail with links to every board it's posted on | Phone layout |
| --- | --- |
| ![Detail drawer](docs/detail.png) | <img src="docs/mobile.png" alt="Phone layout" width="260"> |

## What it does

- **Three scrapers for three kinds of site.** StackJobs is server-rendered with `rel=next` pagination and "Posted 3 days ago" dates. RemoteHub is a JavaScript-only SPA with a token-protected API, a "Load more" button and hash-routed detail pages, so plain HTTP sees nothing. CityCareers has a cookie-consent wall, `DD.MM.YYYY` dates, "(m/f/d)" titles, monthly salaries in schema.org `JobPosting` JSON-LD, and deliberate `503 Retry-After` errors.
- **Normalization that refuses to guess.** `"120–150k EUR"`, `"$60 – $70 an hour"`, `"€55.000 p.a."` and JSON-LD `MonetaryAmount` all become `{min, max, currency, period}`. Text the parser can't read (`"Competitive"`, `"€2,500"` without a period) becomes `null`, not a wrong number.
- **Cross-board de-duplication.** The fingerprint is company + title + place after normalization (`"Sr. Full-Stack Developer (m/f/d)"` at `"Kestrel Media Ltd"` equals `"Senior Full-Stack Developer"` at `"Kestrel Media"`). Postings that share a fingerprint must also agree on remote region, job type and salary range before they're merged. Search shows one listing with links to every board it's on.
- **Jobs close when they disappear, safely.** A run only closes a board's unseen jobs if the listing was complete (the number scraped matches the count the board shows). It refuses to close more than half of a board's jobs at once (`MAX_CLOSE_FRACTION`), because that usually means the scraper broke. Closed jobs that come back are reopened.
- **Incremental scraping.** The backend tells the scraper which listings it already has, with a hash of each. Unchanged listings skip their detail page. A re-scrape of all 131 postings takes about 3 s instead of 15 s and loads only the listing pages. Details older than `DETAIL_MAX_AGE_HOURS` are fetched again anyway, so edits don't get missed.
- **Search.** PostgreSQL full-text search with weighted fields (title and company > skills > city > description). Plain words match as you type (the last word is a prefix). Quotes, `or` and `-word` switch to web-search syntax. Highlighted snippets come back HTML-escaped. Facet counts follow the usual faceted-search rule: each facet applies every filter except its own.
- **Polite crawling.** robots.txt is honoured, images, fonts and media are blocked, detail pages load through a small page pool, and retries use exponential backoff with jitter and respect `Retry-After`.

## How it works

```mermaid
flowchart LR
    subgraph boards["Mock job boards :4010"]
        SJ[StackJobs<br/>SSR + pagination]
        RH[RemoteHub<br/>JS-only SPA]
        CC[CityCareers<br/>consent wall + JSON-LD]
    end
    subgraph scraper["Scrapers (Node + Puppeteer)"]
        L[listing pages] --> K{listing hash<br/>known?}
        K -- no --> D[detail page] --> N[normalize]
        K -- yes --> S[report as seen]
    end
    boards --> L
    N -- "POST /api/ingest/runs/:id/batch" --> API
    S -- seen ids --> API
    subgraph backend["Django + PostgreSQL"]
        API[ingest API<br/>token auth] --> U[upsert + change detection]
        U --> G[fingerprint + regroup<br/>duplicates]
        F["finish run:<br/>close unseen jobs<br/>(if complete and < 50%)"]
        Q[search API<br/>tsvector + facets]
    end
    API --> F
    Q --> UI[Vue 3 frontend]
```

A scrape is one *run* per board: `POST /runs/` → any number of `POST /runs/:id/batch/` (postings and seen ids) → `POST /runs/:id/finish/` with the scraper's own stats and a `complete` flag. Starting a new run abandons a stuck earlier one, and repeating `finish` returns the same answer, so a retried request is harmless.

## Measured results

Measured on this machine with the default seed. `scripts/simulate.mjs` moves the boards forward 5 days at a time, so jobs open and close, scrapes after every step, and scores the database against the boards' ground truth with `scripts/evaluate-dedupe.mjs`:

| Mock day | Open postings | Distinct jobs | Duplicate pairs merged correctly | Wrong merges | Open/closed mismatches |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 131 | 102 | 29 / 29 | 0 | 0 |
| 5 | 136 | 107 | 29 / 29 | 0 | 0 |
| 10 | 137 | 110 | 27 / 27 | 0 | 0 |
| 15 | 139 | 110 | 29 / 29 | 0 | 0 |
| 20 | 129 | 101 | 28 / 28 | 0 | 0 |
| 25 | 113 | 87 | 26 / 26 | 0 | 0 |
| 30 | 85 | 66 | 19 / 19 | 0 | 0 |

The first version matched on fingerprint alone and got 28 of 29 on day 5. One company had two different remote "Frontend Engineer" openings, one worldwide and full-time, one US-only on contract. Those now stay apart because their region and job type conflict, and there's a test for it.

Field accuracy is checked too: `scrapers/test/browser.test.js` crawls every board in a real Chromium and compares every field of every posting (title, company, city, country, workplace, region, job type, salary min/max/currency/period, post date, skills, description structure) with the mock's ground truth. All 131 postings match. The only tolerance is ±3% for RemoteHub's compact `"1.9k EUR/mo"` style.

## Tech stack

- **Scrapers:** Node.js 22 (ESM), puppeteer-core 25 driving Chrome/Chromium, `node:test`. Zero other runtime dependencies.
- **Backend:** Python 3.12, Django 6.1, Django REST Framework 3.18, PostgreSQL 17 (tsvector + GIN, `text[]` tags), psycopg 3, gunicorn, whitenoise. pytest + pytest-django.
- **Frontend:** Vue 3.5 (`<script setup>`), Vite 8, Vitest + Vue Test Utils + happy-dom. No UI library; light and dark themes.
- **Mock boards:** Node.js `http`, no dependencies. Seeded, deterministic data and an admin API to move time.
- **Ops:** Docker Compose (Postgres, Django, mock boards, scraper on a schedule, nginx serving the built frontend), GitHub Actions CI.

## Run it

### Docker

```bash
cp .env.example .env        # optional; the compose file has working defaults
docker compose up --build
```

- App: http://localhost:8080. The scraper service fills it within about a minute and then runs every `SCRAPE_EVERY` (30 min).
- Mock boards: http://localhost:4010 (has a button to move time forward a day)
- Admin: `docker compose exec backend python manage.py createsuperuser`, then http://localhost:8080/admin/

### Without Docker

Needs Python 3.12, Node 22.12+, and Chrome or Chromium. The scraper finds Chrome, Playwright's Chromium or `/usr/bin/chromium` on its own; otherwise set `CHROME_PATH`. PostgreSQL is optional: `DATABASE_URL=embedded` runs a private server from the [`pgserver`](https://pypi.org/project/pgserver/) wheel.

```bash
python -m venv .venv && .venv/Scripts/pip install -r backend/requirements-dev.txt   # .venv/bin/pip on Linux/macOS
(cd scrapers && npm ci) && (cd frontend && npm ci)
cp .env.example .env
node scripts/dev.mjs          # mock boards :4010, Django :8010, one scrape, Vite :5173
```

Then open http://127.0.0.1:5173. Useful next steps:

```bash
cd scrapers && node src/cli.js run                    # scrape again (incremental)
node src/cli.js run --source citycareers --full       # one board, every detail page
node src/cli.js run --out jobs.ndjson                 # dry run to a file, no backend needed
curl -X POST localhost:4010/__admin/tick -d '{"days":3}'   # move the boards 3 days forward
node scripts/simulate.mjs --steps 6 --days 5          # the results table above
```

### Tests

```bash
cd backend && ../.venv/Scripts/python -m pytest       # 77 tests, real PostgreSQL (embedded, or TEST_DATABASE_URL)
cd scrapers && node --test                            # 58 tests, including 4 in real Chromium
cd mockboards && node --test                          # 12 tests
cd frontend && npm test                               # 17 tests
```

The browser tests skip themselves if no Chrome/Chromium is found. Nothing needs network access or an API key.

## Configuration

All settings are environment variables. See [.env.example](.env.example).

| Variable | Default | What it does |
| --- | --- | --- |
| `DATABASE_URL` | `postgres://jobs:jobs@localhost:5432/jobs` | PostgreSQL URL, or `embedded` for a private pgserver instance in `.data/pgdata` |
| `INGEST_TOKEN` | (empty = ingest disabled) | Shared secret; scrapers send `Authorization: Token …` |
| `DETAIL_MAX_AGE_HOURS` | `24` | Re-fetch an unchanged listing's details after this long |
| `MAX_CLOSE_FRACTION` | `0.5` | A run won't close more than this share of a board's open jobs |
| `BOARDS_URL` / `API_URL` | `http://127.0.0.1:4010` / `:8010` | Where the scraper crawls and where it pushes |
| `PUBLIC_BOARDS_URL` | (unset) | Rewrites stored job links (Docker: `mockboards:4010` → `localhost:4010`) |
| `SCRAPE_CONCURRENCY` / `SCRAPE_DELAY_MS` | `3` / `100` | Detail pages in parallel, pause after each page |
| `SCRAPE_EVERY` | `30m` | Interval for `jobscrape run --every` (the compose service) |
| `MOCK_SEED` / `MOCK_FAULTS` | `13` / `1` | Mock data seed; `0` turns off CityCareers' 503s |

## API

| Endpoint | |
| --- | --- |
| `GET /api/jobs/?q=&workplace=&employment_type=&seniority=&source=&country=&tags=&salary_min=&posted_within=&has_salary=&sort=&page=&page_size=` | Search. Lists accept `a,b` or repeated keys; `tags` is AND; `salary_min` is yearly USD. Returns `results`, `count`, `pages` and `facets`. |
| `GET /api/jobs/:id/` | Full job, with `also_on` (other boards) and `canonical_id` if it's a duplicate |
| `GET /api/sources/` | Boards with open/duplicate/closed counts and the last run |
| `GET /api/overview/` | Totals for the header |
| `POST /api/ingest/runs/` → `…/:id/batch/` → `…/:id/finish/` | Scraper ingest (token) |
| `GET /api/ingest/sources/:slug/known/` | `external_id → listing_hash` for skip-unchanged |

Management commands: `ingest_file jobs.ndjson [--complete]` loads a dry-run file. `regroup` rebuilds fingerprints, tags, search vectors and duplicate groups after rule changes. `close_stale --days 7` is a safety net for boards whose runs are never complete.

## Project layout

```
mockboards/   three mock job boards + time-travel admin API (zero deps)
scrapers/     src/sources/*.js (one per board), runner, normalize, retry, robots, sinks, CLI
backend/      config/ (settings, embedded Postgres), jobs/ (models, ingest, search, normalize, skills, API, admin)
frontend/     Vue app: search bar, facet sidebar, result cards, detail drawer, URL-synced state
scripts/      dev.mjs (run everything), simulate.mjs + evaluate-dedupe.mjs (accuracy), screenshot.py
```

## Limitations

- **The boards are mocks.** They are built to show real-world problems (SPA rendering, consent walls, lossy formats, flaky responses), but real boards add CAPTCHAs, login walls, rate limits and terms of service. Check a site's terms and robots.txt before pointing a scraper at it. The source modules are small, so adding a real board means writing one `listings()` + `detail()` pair.
- **De-duplication is rule-based.** It is exact on this data set, and the rules are the kind real boards need (legal suffixes, Sr./Jr., gender markers, region/type/salary conflicts). But two boards that word a title differently ("Backend Engineer" vs "Server-side Developer") won't merge. A fuzzy or embedding-based second pass would be the next step.
- **Salary comparison is coarse.** The salary filter and sort use static exchange rates and annualize hourly rates at 2,080 hours, so contract roles rank high on "highest salary". Unknown currencies are left out of salary filtering.
- **Docker was not run here.** The development machine has no Docker, so the compose file, Dockerfiles, nginx config and CI workflow are untested. Everything else ran for real: the Django backend on PostgreSQL 16 from pgserver, the scrapers in Chromium 1223, and the results above.
- **Single scraper process.** Runs for one board are serialized by the backend (a new run abandons the previous one). There is no distributed queue; a real deployment would schedule boards separately (cron, Celery beat).

## Troubleshooting

- `initdb: error: could not fsync file … Bad file descriptor` on Windows: an earlier embedded Postgres was still releasing its files. Delete `.data/pgdata` and run again.
- `Port 8010 … is already in use`: `scripts/dev.mjs` refuses to share ports rather than talk to another app.
- The Windows `pgserver` wheel ships without PostgreSQL's time-zone files. `backend/config/embedded.py` copies them from the `tzdata` package on first use; without them Postgres rejects even `TimeZone=UTC`.

## sort entries

Updated implementation details.

## validate request

Updated implementation details.