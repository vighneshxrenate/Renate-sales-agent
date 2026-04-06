---
name: Project status — scraping + enrichment pipeline working
description: Current state of Renate sales agent as of 2026-04-06, pushed to feature/rishi-work
type: project
---

Branch: `feature/rishi-work` — pushed to origin (2026-04-06)

## What's working
- **Naukri scraper**: Intercepts `/jobapi/v3/search` JSON API, structured lead extraction, no LLM needed
- **LinkedIn scraper**: DOM selector extraction from guest job search (`base-card`, `base-search-card__title`), structured leads
- **Enrichment pipeline**: Apollo org → Hunter HR dept → DuckDuckGo dork → Google dork → SMTP verify → Google search → contact pages
- **Indian phone validator**: STD code validation, known junk blacklist, mobile/landline/toll-free format checks
- **Results**: ~82% email coverage, ~59% HR recruiter emails, ~91% validated phones, 0 junk
- **Docker**: 4 services (db, playwright-browser, backend, frontend) all running
- **Frontend**: Next.js on :3001, API docs on :8000/docs

## Known issues
- Google Jobs scraper: code complete but container IP gets flagged by Google after testing; works on fresh IPs with consent cookies + 2Captcha
- Apollo free tier: people search API requires paid plan ($49/mo); org enrich works free
- Hunter free tier: 50 searches/month; user has key `ec9be7c8...`
- Naukri sometimes times out via proxy; works without proxy
- Indeed, Glassdoor scrapers: untested
- Enrichment is slow (~15-20s per lead with all fallbacks)

## Key files
- `backend/app/scraper/sources/naukri.py` — Naukri API intercept scraper
- `backend/app/scraper/sources/linkedin.py` — LinkedIn DOM scraper
- `backend/app/services/enrichment_service.py` — 7-step enrichment pipeline
- `backend/app/services/apollo_client.py` — Apollo.io client
- `backend/app/services/hunter_client.py` — Hunter.io client
- `backend/app/services/email_discovery.py` — Google/DDG dork + SMTP verify
- `backend/app/utils/phone_validator.py` — Indian phone number validation
- `backend/app/utils/dedup.py` — Lead deduplication with selectinload fix

**Why:** Track what's been built and what still needs work for future sessions.

**How to apply:** Reference this when picking up work. Check git log for latest commits.
