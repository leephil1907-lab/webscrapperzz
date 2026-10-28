# Webscrapperzz Intelligence

A responsive crawler and website-recovery research tool for public websites, with a polished multi-view workspace.

## Current capabilities

- Crawl linked public HTML pages within a configurable same-domain scope.
- Discover URLs through common sitemap files and sitemap declarations in `robots.txt`.
- Extract page titles, descriptions, canonical URLs, language, headings, visible text, word counts, public email candidates, phone candidates, social links, image references, response headers, and JSON-LD structured data.
- Record HTTP failures and crawl errors; export JSON, CSV, and Markdown reports.
- Inspect a dead or broken site's DNS and HTTP/HTTPS responses without requiring its hostname to resolve first.
- Query the Internet Archive Wayback Machine for closest snapshots and historical page candidates.
- Responsive application shell with sidebar navigation, mobile drawer, overview metrics, deep crawl workspace, site recovery report, job history filters, and API guide.\n- Standard result tabs for pages, contacts, social profiles, assets/structured data, and errors.\n- Smooth page transitions, reduced-motion support, keyboard focus states, accessible labels, and responsive mobile tables.\n- Dashboard includes both **Start deep crawl** and **Recover a dead / broken site** workflows.
- FastAPI endpoints with interactive API docs at `/docs`.

## Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open `http://127.0.0.1:8000`. Health check: `/health`.

## Deploy with Docker

```bash
docker build -t webscrapperzz .
docker run --rm -p 8000:8000 -e PORT=8000 webscrapperzz
```

The container uses the configured `PORT` environment variable, defaulting to 8000.

## API

- `POST /api/crawls` — create a crawl job. Example JSON: `{"url":"https://example.com","max_pages":50,"respect_robots":true,"include_subdomains":false,"recover_archives":true}`
- `GET /api/crawls/{id}` — get crawl status and extracted data.
- `GET /api/crawls` — list recent in-memory jobs.
- `GET /api/crawls/{id}/export?format=json|csv|markdown` — export a completed crawl.
- `POST /api/recover` — inspect a broken/dead target and query Internet Archive. Example JSON: `{"url":"old-example-domain.com","inspect_sitemaps":true,"archive_lookup":true}`
- `GET /health` — health check.

## What "dead site recovery" can and cannot do

If the origin is down, the tool cannot recover content that no longer exists anywhere accessible. It can still report DNS failure and search Internet Archive's availability and CDX indexes for historic snapshots. Those pages may be incomplete, unavailable, or out of date. For the best recovery odds, try the root domain and important old page URLs separately, and compare any snapshots with backups, exports, CMS databases, or search-engine results you already own.

This application does not bypass authentication, paywalls, CAPTCHAs, robots restrictions, or access controls. It does not guarantee extraction of every possible fact. JavaScript-heavy pages may require an isolated browser worker, and PDFs are currently detected but their text is not yet extracted.

## Production readiness

Crawl jobs are currently stored in process memory and disappear on restart. Before exposing the service publicly, add authentication, quotas, persistent storage, a background queue, request rate limiting, and stronger network egress protections. Recovery checks deliberately avoid following user-site redirects automatically. Review site policies, privacy obligations, and applicable law before crawling.
