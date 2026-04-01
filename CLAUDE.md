# Renate Sales Agent

AI-powered lead scraper that finds companies actively hiring in India, extracts emails/phones/positions, and delivers daily reports.

## Current Status

**Phases 1–4 complete. Next up: Phase 5 (Enrichment + Dedup).**

Branch `V-phase3` has all work so far (Phases 1–4). See `PLAN.md` for the full 8-phase roadmap.

## Architecture

- **Backend**: FastAPI (async) + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL 16
- **Scraping**: Playwright (remote browser via WebSocket) + stealth patches + rotating residential proxies
- **AI Extraction**: Claude API (claude-sonnet-4-6) — HTML → structured lead data
- **Frontend**: Next.js (App Router) + shadcn/ui + TanStack Query
- **Deployment**: Docker Compose (4 services: db, playwright-browser, backend, frontend)

## Key Files

### Backend core
- `backend/app/main.py` — FastAPI app, lifespan (initializes proxy pool → browser pool → captcha solver → scraper manager, registers all 6 scrapers)
- `backend/app/config.py` — Pydantic Settings (all config via env vars)
- `backend/app/db/` — async SQLAlchemy engine + session
- `backend/app/models/` — Lead, LeadEmail, LeadPhone, HiringPosition, ScrapeJob, DailyReport, Proxy
- `backend/app/schemas/` — Pydantic request/response models
- `backend/app/api/` — REST endpoints: leads CRUD, jobs trigger/cancel, reports, health
- `backend/app/services/` — lead_service, job_service, report_service, ai_extraction

### Scraping engine
- `backend/app/scraper/manager.py` — Job orchestrator: asyncio queue + workers → scrape → AI extract → dedup → store leads
- `backend/app/scraper/browser_pool.py` — Browser context pool with 10 fingerprints, semaphore concurrency
- `backend/app/scraper/proxy_pool.py` — Proxy rotation with DB sync, cooldown, health check
- `backend/app/scraper/stealth.py` — Anti-detection JS patches (webdriver, WebGL, canvas, chrome object)
- `backend/app/scraper/human_behavior.py` — Human simulation (typing, scrolling, delays)
- `backend/app/scraper/captcha_solver.py` — 2Captcha integration (reCAPTCHA + hCaptcha)
- `backend/app/scraper/base.py` — BaseScraper ABC + ScraperResult dataclass

### Source scrapers
- `backend/app/scraper/sources/google_jobs.py`
- `backend/app/scraper/sources/career_page.py`
- `backend/app/scraper/sources/linkedin.py`
- `backend/app/scraper/sources/naukri.py`
- `backend/app/scraper/sources/indeed.py`
- `backend/app/scraper/sources/glassdoor.py`
- `backend/app/scraper/fallback/apify_client.py`
- `backend/app/scraper/fallback/firecrawl_client.py`

## What's Left (Phases 5–8)

### Phase 5: Enrichment + Dedup
- `backend/app/utils/email_patterns.py` — Pattern guessing (info@, hr@, first.last@)
- `backend/app/utils/dns_discovery.py` — MX record lookup, email verification
- `backend/app/utils/dedup.py` — Fuzzy company name matching (thefuzz + domain)
- `backend/app/services/enrichment_service.py` — Visit /contact + /about pages, combine sources
- Wire enrichment into `manager.py` pipeline (after AI extraction, before storage)

### Phase 6: Frontend
- Dashboard with stats cards + charts
- Leads page (DataTable, filters, search, export, detail view)
- Jobs page (trigger dialog, progress polling)
- Reports page (list + detail with charts)
- Frontend stubs already exist in `frontend/src/` — hooks and pages are scaffolded

### Phase 7: Scheduling + Reports
- APScheduler: daily 9 AM scrape, proxy health every 15 min
- Report generation + email delivery (aiosmtplib)

### Phase 8: Hardening
- Retry logic (tenacity) in scrapers
- Structured logging (structlog)
- Error handling for Claude API failures
- Rate limiting on API endpoints

## Conventions

- Python async/await throughout the backend
- Environment variables for all secrets (see `.env.example`)
- Scraper sources extend `BaseScraper` and register via `scraper_manager.register_scraper()`
- India-focused geography (Bangalore, Mumbai, Delhi, Hyderabad, Pune, Chennai)
- SmartProxy for residential proxies (Indian IPs for Naukri)
- httpx for HTTP client needs, aiohttp also available as dependency
