# Webscrapperzz Intelligence

A responsive website crawling and structured extraction application.

## Features

- Crawl linked public HTML pages within a configurable same-domain scope.
- Extract page titles, descriptions, canonical URLs, language, headings, visible text, word counts, public email candidates, phone candidates, social links, image assets, and JSON-LD data.
- Crawl progress, error records, recent job listing, and JSON/CSV/Markdown exports.
- Configurable page cap, robots.txt preference, and optional subdomain crawling.
- FastAPI backend and responsive dashboard.

## Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://127.0.0.1:8000. Health check: `/health`. API docs: `/docs`.

## Deploy with Docker

Build the included Dockerfile and expose the assigned `PORT` environment variable (defaults to 8000).

## API

- `POST /api/crawls` — create a crawl job. Example JSON: `{"url":"https://example.com","max_pages":50,"respect_robots":true,"include_subdomains":false}`
- `GET /api/crawls/{id}` — get job status and extracted data.
- `GET /api/crawls` — recent in-memory jobs.
- `GET /api/crawls/{id}/export?format=json|csv|markdown` — download completed crawl.
- `GET /health` — health check.

## Production readiness

This initial version uses HTTP HTML fetching and does not execute JavaScript in a browser. Crawl jobs are stored in process memory and are lost on restart. Before opening the service to untrusted users, add authentication, per-user quotas, persistent storage, a background queue, request rate limiting, and hardened network egress controls. The URL validator blocks local and non-public IP targets and validates redirect destinations, but production SSRF defense should additionally pin validated DNS results at connection time. Site owners' rules, robots directives, privacy obligations, and rate limits should be respected.

## Roadmap

1. Isolated browser-rendering worker (Crawl4AI or Playwright) for JavaScript-heavy sites.
2. PostgreSQL persistence and Redis-backed task queue.
3. Sitemap discovery, stronger canonical deduplication, structured extraction profiles, PDF reports.
4. Authenticated workspaces, quotas, scheduled crawls, change tracking, and webhook delivery.
5. Review upstream licenses and dependencies before embedding code; this project implements an original integration and does not vendor the referenced projects.
