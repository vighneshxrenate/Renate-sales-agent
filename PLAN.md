# Renate Sales Agent — AI Lead Scraper

## Context

Building a greenfield AI-powered lead scraper that discovers companies actively hiring, extracts their contact info (emails, phones), and delivers daily reports. The core challenge is scraping anti-bot protected sites (LinkedIn, Naukri) reliably while extracting structured data from wildly varying career page formats using Claude AI.

## Tech Stack (Locked In)

- **Frontend**: Next.js (App Router) + shadcn/ui + TanStack Query
- **Backend**: FastAPI (async) + SQLAlchemy 2.0 (async) + Alembic
- **Database**: PostgreSQL 16
- **Scraping**: Playwright + playwright-stealth + rotating residential proxies + 2Captcha
- **AI Extraction**: Claude API (sonnet for extraction, structured output)
- **Scheduling**: APScheduler (in-process)
- **Deployment**: Docker Compose (4 services: db, playwright-browser, backend, frontend)
- **Proxies**: SmartProxy recommended (best price/quality for Indian residential IPs, ~$8/GB, API for rotation). BrightData as alternative. Proxy pool abstracted so provider is swappable.
- **Geography**: India-focused (Bangalore, Mumbai, Delhi, Hyderabad, Pune, Chennai)
- **Reports**: Email (SMTP) + Dashboard. Daily 9 AM scrape → report emailed to configured recipients.

## Project Structure

```
renate-sales-agent/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   └── app/
│       ├── main.py                 # FastAPI app, lifespan, middleware
│       ├── config.py               # Pydantic Settings
│       ├── db/                     # engine, session, base
│       ├── models/                 # lead, lead_email, lead_phone, hiring_position, scrape_job, daily_report, proxy
│       ├── schemas/                # Pydantic request/response models
│       ├── api/                    # leads, jobs, reports, health endpoints
│       ├── services/
│       │   ├── lead_service.py
│       │   ├── job_service.py
│       │   ├── report_service.py
│       │   ├── enrichment_service.py   # email/phone discovery
│       │   ├── ai_extraction.py        # Claude API: HTML → structured leads
│       │   └── email_sender.py
│       ├── scraper/
│       │   ├── base.py             # AbstractScraper interface
│       │   ├── manager.py          # Job orchestration, pipeline
│       │   ├── browser_pool.py     # Fingerprint rotation, context management
│       │   ├── proxy_pool.py       # Rotation, health, cooldown
│       │   ├── stealth.py          # Anti-detection patches
│       │   ├── human_behavior.py   # Delays, scrolling, typing simulation
│       │   ├── captcha_solver.py   # 2Captcha integration
│       │   ├── sources/
│       │   │   ├── linkedin.py
│       │   │   ├── naukri.py
│       │   │   ├── indeed.py
│       │   │   ├── glassdoor.py
│       │   │   ├── career_page.py
│       │   │   └── google_jobs.py
│       │   └── fallback/
│       │       ├── apify_client.py
│       │       └── firecrawl_client.py
│       ├── scheduler/
│       │   └── jobs.py             # APScheduler config (9 AM daily, proxy health)
│       └── utils/
│           ├── dedup.py            # Fuzzy company name matching
│           ├── email_patterns.py   # Pattern guessing (info@, hr@, first.last@)
│           ├── dns_discovery.py    # MX record lookup, email verification
│           └── csv_export.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── app/
│       │   ├── layout.tsx          # Sidebar nav
│       │   ├── page.tsx            # Dashboard: stats + charts
│       │   ├── leads/              # Table + detail view
│       │   ├── jobs/               # Job list + trigger + detail
│       │   └── reports/            # Report list + detail
│       ├── components/
│       │   ├── ui/                 # shadcn/ui
│       │   ├── layout/             # Sidebar, Header
│       │   ├── leads/              # LeadsTable, LeadFilters, ExportButton
│       │   ├── jobs/               # JobsTable, TriggerJobDialog, JobProgress
│       │   └── reports/            # ReportCard, ReportCharts
│       ├── lib/
│       │   ├── api.ts              # Fetch wrapper
│       │   └── types.ts            # TS types mirroring backend schemas
│       └── hooks/                  # useLeads, useJobs, useReports (TanStack Query)
└── playwright-browser/
    └── Dockerfile
```

## Database Schema

### `leads`
`id` (UUID PK), `company_name`, `company_name_normalized` (indexed, for dedup), `location`, `location_normalized`, `website`, `industry`, `company_size`, `description`, `source` (linkedin/naukri/indeed/career_page/etc), `source_url`, `confidence_score` (0-1 from AI), `status` (new/contacted/qualified/disqualified), `scrape_job_id` (FK), `merged_into_id` (self-ref FK for dedup), `created_at`, `updated_at`

### `lead_emails`
`id`, `lead_id` (FK), `email`, `email_type` (generic/personal/hr/careers), `source` (scraped/pattern_guess/dns), `verified` (bool)

### `lead_phones`
`id`, `lead_id` (FK), `phone`, `phone_type` (main/hr/mobile)

### `hiring_positions`
`id`, `lead_id` (FK), `title`, `department`, `location`, `job_type`, `experience_level`, `salary_range`, `posted_date`, `source_url`, `raw_text`

### `scrape_jobs`
`id`, `source`, `keywords`, `location_filter`, `status` (pending/running/completed/failed/cancelled), `triggered_by` (manual/scheduled), `total_pages`, `pages_scraped`, `leads_found`, `leads_new`, `error_message`, `started_at`, `completed_at`

### `daily_reports`
`id`, `report_date` (unique), `total_leads_found`, `new_leads`, `leads_by_source` (JSONB), `leads_by_location` (JSONB), `top_hiring_positions` (JSONB), `scrape_jobs_run`, `scrape_jobs_failed`, `email_sent`

### `proxies`
`id`, `protocol`, `host`, `port`, `username`, `password`, `provider`, `is_active`, `last_used_at`, `cooldown_until`, `fail_count`, `success_count`, `avg_response_ms`

## Scraping Pipeline

```
Trigger (manual or 9 AM scheduler)
  → ScraperJobManager submits jobs to asyncio.Queue
  → Up to 3 concurrent scrapers run
  → Each scraper yields ScraperResult (raw HTML) via AsyncGenerator
  → AI Extraction (Claude): HTML → structured lead data
  → Enrichment: visit /contact + /about pages, email pattern guessing, MX verification
  → Dedup: fuzzy match on normalized (company_name, location) + domain match
  → Store: insert new or merge into existing lead
  → On daily completion: generate report
```

## Anti-Detection Strategy

| Source | IP Layer | Browser | Behavior | Fallback |
|--------|----------|---------|----------|----------|
| **LinkedIn** | Residential proxies, session-pinned, US/India geo | Stealth + real fingerprint + logged-in burner accounts | 2-5s delays, 100 req/session max, visit non-job pages randomly | Apify actor |
| **Naukri** | Indian residential proxies only | Stealth + Cloudflare bypass | 3-6s delays, 15 pages/session | Apify actor |
| **Indeed/Glassdoor** | Residential, geo-matched | Standard stealth | 1-3s delays | Indeed RSS, SerpAPI |
| **Career Pages** | Datacenter proxies (cheaper) | Minimal stealth, respect robots.txt | 2s/request/domain | Firecrawl for heavy SPAs |

**Proxy Provider Recommendation**: SmartProxy — best price for Indian residential IPs (~$8/GB), sticky sessions up to 30 min (good for LinkedIn session pinning), geo-targeting at city level, API for proxy list management. Set up with their rotating residential gateway: `gate.smartproxy.com:10001`. The proxy pool module will abstract the provider so switching to BrightData or Oxylabs later is a config change.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/leads` | List (paginated, filterable, searchable) |
| GET | `/api/leads/{id}` | Detail with emails, phones, positions |
| PATCH | `/api/leads/{id}` | Update status |
| DELETE | `/api/leads/{id}` | Delete |
| GET | `/api/leads/export` | CSV export (streaming) |
| GET | `/api/leads/stats` | Aggregate stats |
| POST | `/api/jobs` | Trigger scrape job |
| GET | `/api/jobs` | List jobs |
| GET | `/api/jobs/{id}` | Job detail + progress |
| POST | `/api/jobs/{id}/cancel` | Cancel job |
| GET | `/api/reports` | List reports |
| GET | `/api/reports/{id}` | Report detail |
| POST | `/api/reports/generate` | Manual report trigger |
| GET | `/api/health` | Health check |

## Docker Services

1. **db**: postgres:16-alpine (port 5432)
2. **playwright-browser**: MS Playwright image, `launch-server` on port 3000 (4GB RAM limit)
3. **backend**: Python 3.12, single uvicorn worker (APScheduler is in-process), port 8000
4. **frontend**: Next.js, port 3001

Single uvicorn worker because APScheduler + browser pool + proxy pool are in-process singletons.

## Implementation Order

### Phase 1: Foundation ✅ DONE
- Project scaffolding (docker-compose, Dockerfiles, pyproject.toml, Next.js init)
- Database: SQLAlchemy models, Alembic setup, initial migration
- FastAPI app shell with health endpoint
- Verify: `docker compose up` boots all 4 services

### Phase 2: Core Backend ✅ DONE
- Pydantic schemas
- Lead CRUD API + search + CSV export
- Scrape job API + report API
- PostgreSQL trigram index for full-text search

### Phase 3: Scraping Infrastructure ✅ DONE
- Proxy pool (rotation, health check, cooldown)
- Browser pool (fingerprints, context lifecycle, stealth patches)
- Human behavior simulation (delays, scroll, type)
- CAPTCHA solver integration (2Captcha)
- Abstract scraper interface + job manager

### Phase 4: Source Scrapers ✅ DONE
1. Google Jobs (least defended — validates full pipeline)
2. Career page scraper + AI extraction service (Claude API)
3. LinkedIn scraper (hardest — full anti-detection)
4. Naukri scraper (Cloudflare handling)
5. Indeed + Glassdoor
6. Fallback clients (Apify, Firecrawl)

### Phase 5: Enrichment + Dedup ⬅️ START HERE
- Email/phone discovery (contact pages, pattern guessing, MX lookup)
- Fuzzy dedup engine (thefuzz + domain matching)
- Full pipeline integration test

### Phase 6: Frontend
- Layout + sidebar nav
- Dashboard (stats cards + charts)
- Leads page (DataTable, filters, search, export, detail view)
- Jobs page (table, trigger dialog, progress polling)
- Reports page (list + detail with charts)

### Phase 7: Scheduling + Reports
- APScheduler: daily 9 AM scrape, proxy health every 15 min
- Report generation logic + optional email delivery

### Phase 8: Hardening
- Retry logic (tenacity) in scrapers
- Structured logging (structlog)
- Error handling for Claude API failures
- Rate limiting on API endpoints

## Verification

1. `docker compose up` — all 4 services boot, health check passes
2. Trigger a scrape job via API/dashboard → job runs → leads appear in DB + dashboard
3. Verify dedup: same company from 2 sources → single lead with merged data
4. Verify enrichment: leads have emails/phones discovered beyond what was on the job listing
5. Verify daily schedule: set scheduler to run in 1 minute, confirm report generates
6. Export CSV → opens in spreadsheet with all lead data
