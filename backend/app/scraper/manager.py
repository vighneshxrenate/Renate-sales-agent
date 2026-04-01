import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import update

from app.config import settings
from app.db.engine import async_session
from app.models.scrape_job import ScrapeJob
from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.browser_pool import BrowserPool
from app.scraper.captcha_solver import CaptchaSolver
from app.scraper.proxy_pool import ProxyPool

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

            # TODO: Phase 4+ will add AI extraction, enrichment, dedup here
            await self._update_job_status(
                job_id,
                "completed",
                completed_at=datetime.now(timezone.utc),
                pages_scraped=pages_scraped,
                leads_found=0,
                leads_new=0,
            )
            logger.info("scraper_manager.job_completed", job_id=job_id_str, pages=pages_scraped)

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
