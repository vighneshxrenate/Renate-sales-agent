import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, update

from app.config import settings
from app.db.engine import async_session
from app.models.job_position import HiringPosition
from app.models.lead import Lead, LeadEmail, LeadPhone
from app.models.scrape_job import ScrapeJob
from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.browser_pool import BrowserPool
from app.scraper.captcha_solver import CaptchaSolver
from app.scraper.proxy_pool import ProxyPool
from app.services.ai_extraction import AIExtractionService

logger = structlog.get_logger()


class ScraperJobManager:
    def __init__(
        self,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
        captcha_solver: CaptchaSolver,
    ):
        self._browser_pool = browser_pool
        self._proxy_pool = proxy_pool
        self._captcha_solver = captcha_solver
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._registry: dict[str, type[BaseScraper]] = {}
        self._ai_extraction = AIExtractionService()

    def register_scraper(self, source_name: str, scraper_class: type[BaseScraper]) -> None:
        self._registry[source_name] = scraper_class
        logger.info("scraper.registered", source=source_name)

    def has_scraper(self, source: str) -> bool:
        return source in self._registry

    @property
    def registered_sources(self) -> list[str]:
        return list(self._registry.keys())

    async def start(self) -> None:
        for i in range(settings.max_concurrent_scrapers):
            task = asyncio.create_task(self._worker_loop(i))
            self._workers.append(task)
        logger.info("scraper_manager.started", workers=settings.max_concurrent_scrapers)

    async def submit(
        self,
        job_id: UUID,
        source: str,
        keywords: str,
        location: str | None,
        max_pages: int,
    ) -> None:
        cancel_event = asyncio.Event()
        self._cancel_events[str(job_id)] = cancel_event
        await self._queue.put({
            "job_id": job_id,
            "source": source,
            "keywords": keywords,
            "location": location,
            "max_pages": max_pages,
            "cancel_event": cancel_event,
        })
        logger.info("scraper_manager.job_submitted", job_id=str(job_id), source=source)

    async def cancel(self, job_id: UUID) -> None:
        key = str(job_id)
        if key in self._cancel_events:
            self._cancel_events[key].set()
            logger.info("scraper_manager.job_cancelled", job_id=key)

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            try:
                job = await self._queue.get()
                await self._run_job(job, worker_id)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("scraper_manager.worker_error", worker_id=worker_id)

    async def _run_job(self, job: dict, worker_id: int) -> None:
        job_id = job["job_id"]
        job_id_str = str(job_id)
        cancel_event: asyncio.Event = job["cancel_event"]

        await self._update_job_status(job_id, "running", started_at=datetime.now(timezone.utc))
        logger.info("scraper_manager.job_started", job_id=job_id_str, worker=worker_id)

        try:
            scraper = self._get_scraper(job["source"])
            pages_scraped = 0
            results: list[ScraperResult] = []

            async for result in scraper.scrape(
                keywords=job["keywords"],
                location=job["location"],
                max_pages=job["max_pages"],
            ):
                if cancel_event.is_set():
                    await self._update_job_status(job_id, "cancelled")
                    logger.info("scraper_manager.job_cancelled_mid_run", job_id=job_id_str)
                    return

                pages_scraped += 1
                results.append(result)
                await self._update_job_progress(job_id, pages_scraped)

            # AI extraction → lead storage
            leads_found = 0
            leads_new = 0
            for result in results:
                extracted = await self._ai_extraction.extract_leads(
                    result.raw_html, result.source_url, result.source_name
                )
                for company_data in extracted:
                    leads_found += 1
                    is_new = await self._store_lead(company_data, job_id)
                    if is_new:
                        leads_new += 1

            await self._update_job_status(
                job_id,
                "completed",
                completed_at=datetime.now(timezone.utc),
                pages_scraped=pages_scraped,
                leads_found=leads_found,
                leads_new=leads_new,
            )
            logger.info(
                "scraper_manager.job_completed",
                job_id=job_id_str,
                pages=pages_scraped,
                leads_found=leads_found,
                leads_new=leads_new,
            )

        except Exception as e:
            logger.exception("scraper_manager.job_failed", job_id=job_id_str)
            await self._update_job_status(
                job_id, "failed", error_message=str(e),
                completed_at=datetime.now(timezone.utc),
            )
        finally:
            self._cancel_events.pop(job_id_str, None)

    def _get_scraper(self, source: str) -> BaseScraper:
        scraper_class = self._registry.get(source)
        if not scraper_class:
            raise ValueError(f"No scraper registered for source: {source}")
        return scraper_class(self._browser_pool, self._captcha_solver)

    async def _update_job_status(self, job_id: UUID, status: str, **kwargs) -> None:
        try:
            async with async_session() as db:
                values = {"status": status, **kwargs}
                await db.execute(
                    update(ScrapeJob).where(ScrapeJob.id == job_id).values(**values)
                )
                await db.commit()
        except Exception:
            logger.exception("scraper_manager.status_update_failed", job_id=str(job_id))

    async def _store_lead(self, data: dict, job_id: UUID) -> bool:
        """Store extracted lead in DB. Returns True if it's a new lead."""
        company_name = data.get("company_name", "").strip()
        if not company_name:
            return False

        normalized_name = company_name.lower().strip()
        location = data.get("location")
        normalized_location = location.lower().strip() if location else None

        try:
            async with async_session() as db:
                # Check for existing lead (dedup)
                query = select(Lead).where(
                    Lead.company_name_normalized == normalized_name
                )
                if normalized_location:
                    query = query.where(Lead.location_normalized == normalized_location)
                existing = (await db.execute(query)).scalar_one_or_none()

                if existing:
                    # Merge new data into existing lead
                    for field in ("website", "industry", "company_size", "description"):
                        new_val = data.get(field)
                        if new_val and not getattr(existing, field):
                            setattr(existing, field, new_val)
                    await db.commit()
                    return False

                lead = Lead(
                    company_name=company_name,
                    company_name_normalized=normalized_name,
                    location=location,
                    location_normalized=normalized_location,
                    website=data.get("website"),
                    industry=data.get("industry"),
                    company_size=data.get("company_size"),
                    description=data.get("description"),
                    source=data.get("source", "unknown"),
                    source_url=data.get("source_url", ""),
                    confidence_score=data.get("confidence_score"),
                    scrape_job_id=job_id,
                )
                db.add(lead)
                await db.flush()

                for email_data in data.get("emails", []):
                    db.add(LeadEmail(
                        lead_id=lead.id,
                        email=email_data["email"],
                        email_type=email_data.get("email_type"),
                        source="scraped",
                    ))

                for phone_data in data.get("phones", []):
                    db.add(LeadPhone(
                        lead_id=lead.id,
                        phone=phone_data["phone"],
                        phone_type=phone_data.get("phone_type"),
                    ))

                for pos_data in data.get("positions", []):
                    db.add(HiringPosition(
                        lead_id=lead.id,
                        title=pos_data.get("title", "Unknown"),
                        department=pos_data.get("department"),
                        location=pos_data.get("location"),
                        job_type=pos_data.get("job_type"),
                        experience_level=pos_data.get("experience_level"),
                        salary_range=pos_data.get("salary_range"),
                        source_url=pos_data.get("source_url"),
                    ))

                await db.commit()
                return True

        except Exception:
            logger.exception("scraper_manager.store_lead_failed", company=company_name)
            return False

    async def _update_job_progress(self, job_id: UUID, pages_scraped: int) -> None:
        try:
            async with async_session() as db:
                await db.execute(
                    update(ScrapeJob)
                    .where(ScrapeJob.id == job_id)
                    .values(pages_scraped=pages_scraped)
                )
                await db.commit()
        except Exception:
            logger.exception("scraper_manager.progress_update_failed", job_id=str(job_id))

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._cancel_events.clear()
        logger.info("scraper_manager.stopped")
