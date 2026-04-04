import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.engine import async_session
from app.models.lead import Lead, LeadEmail, LeadPhone
from app.models.job_position import HiringPosition
from app.models.scrape_job import ScrapeJob
from app.scraper.base import SCRAPERS, ScraperResult
from app.scraper.browser_pool import BrowserPool
from app.scraper.proxy_pool import ProxyPool
from app.services.ai_extraction import AIExtractionService, ExtractedLead
from app.services.enrichment_service import EnrichmentService
from app.utils.dedup import find_duplicate, merge_leads, normalize_company_name, normalize_location

logger = structlog.get_logger()


class ScraperJobManager:
    def __init__(self, browser_pool: BrowserPool, proxy_pool: ProxyPool) -> None:
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._browser_pool = browser_pool
        self._proxy_pool = proxy_pool
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_scrapers)
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._ai_service = AIExtractionService()
        self._enrichment_service = EnrichmentService()

    async def start(self) -> None:
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(settings.max_concurrent_scrapers)
        ]
        logger.info("scraper_manager_started", workers=settings.max_concurrent_scrapers)

    async def stop(self) -> None:
        self._running = False
        for _ in self._workers:
            await self._queue.put(UUID(int=0))  # sentinel
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        logger.info("scraper_manager_stopped")

    async def submit(self, job_id: UUID) -> None:
        await self._queue.put(job_id)
        logger.info("job_submitted", job_id=str(job_id))

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                job_id = await self._queue.get()
                if job_id == UUID(int=0):
                    break
                async with self._semaphore:
                    await self._process_job(job_id, worker_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("worker_error", worker_id=worker_id)

    async def _process_job(self, job_id: UUID, worker_id: int) -> None:
        async with async_session() as db:
            job = (await db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))).scalar_one_or_none()
            if not job:
                logger.error("job_not_found", job_id=str(job_id))
                return

            if job.status == "cancelled":
                return

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info("job_started", job_id=str(job_id), source=job.source, worker=worker_id)

            scraper_cls = SCRAPERS.get(job.source)
            if not scraper_cls:
                job.status = "failed"
                job.error_message = f"Unknown source: {job.source}"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            scraper = scraper_cls()
            leads_found = 0
            leads_new = 0

            try:
                async for result in scraper.scrape(job, self._browser_pool, self._proxy_pool):
                    if job.status == "cancelled":
                        break

                    job.pages_scraped = result.page_number
                    await db.commit()

                    try:
                        if result.structured_leads is not None:
                            extracted = result.structured_leads
                        else:
                            extracted = await self._ai_service.extract_leads(
                                result.raw_html, result.source, result.url
                            )
                    except Exception:
                        logger.exception("ai_extraction_failed", url=result.url)
                        continue

                    for lead_data in extracted:
                        leads_found += 1
                        try:
                            is_new = await self._store_lead(db, lead_data, job)
                            if is_new:
                                leads_new += 1
                        except Exception:
                            logger.exception("lead_store_failed", company=lead_data.company_name)

                    job.leads_found = leads_found
                    job.leads_new = leads_new
                    await db.commit()

                job.status = "completed"
            except Exception as e:
                logger.exception("job_failed", job_id=str(job_id))
                job.status = "failed"
                job.error_message = str(e)[:2000]

            job.completed_at = datetime.now(timezone.utc)
            job.leads_found = leads_found
            job.leads_new = leads_new
            await db.commit()
            logger.info("job_finished", job_id=str(job_id), status=job.status, found=leads_found, new=leads_new)

    async def _store_lead(self, db: AsyncSession, data: ExtractedLead, job: ScrapeJob) -> bool:
        company_norm = normalize_company_name(data.company_name)
        location_norm = normalize_location(data.location) if data.location else None

        existing = await find_duplicate(db, company_norm, location_norm, data.website)

        if existing:
            await merge_leads(db, existing, data)
            return False

        lead = Lead(
            company_name=data.company_name,
            company_name_normalized=company_norm,
            location=data.location,
            location_normalized=location_norm,
            website=data.website,
            industry=data.industry,
            company_size=data.company_size,
            description=data.description,
            source=data.source,
            source_url=data.source_url,
            confidence_score=data.confidence_score,
            scrape_job_id=job.id,
        )
        db.add(lead)
        await db.flush()

        for email_str, email_type in data.emails:
            db.add(LeadEmail(lead_id=lead.id, email=email_str, email_type=email_type, source="scraped"))

        for phone_str, phone_type in data.phones:
            db.add(LeadPhone(lead_id=lead.id, phone=phone_str, phone_type=phone_type))

        for pos in data.positions:
            db.add(HiringPosition(
                lead_id=lead.id,
                title=pos.get("title"),
                department=pos.get("department"),
                location=pos.get("location"),
                job_type=pos.get("job_type"),
                experience_level=pos.get("experience_level"),
                salary_range=pos.get("salary_range"),
                source_url=pos.get("source_url"),
                raw_text=pos.get("raw_text"),
            ))

        await db.flush()

        try:
            await self._enrichment_service.enrich_lead(
                lead, self._browser_pool, self._proxy_pool, db
            )
        except Exception:
            logger.exception("enrichment_failed", lead_id=str(lead.id))

        return True
