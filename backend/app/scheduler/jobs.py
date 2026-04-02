import asyncio
from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import settings
from app.db.engine import async_session
from app.models.scrape_job import ScrapeJob
from app.services.email_sender import send_report_email
from app.services.report_service import ReportService

logger = structlog.get_logger()


async def daily_scrape_job(app_state) -> None:
    """Triggered daily at configured hour. Creates scrape jobs for all sources."""
    logger.info("daily_scrape_triggered")

    manager = getattr(app_state, "scraper_manager", None)
    if not manager:
        logger.warning("daily_scrape_skipped", reason="scraper_manager not available")
        return

    sources = ["google_jobs", "linkedin", "naukri", "indeed"]
    keywords = "hiring"
    locations = ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Pune", "Chennai"]

    async with async_session() as db:
        for source in sources:
            for location in locations:
                job = ScrapeJob(
                    source=source,
                    keywords=keywords,
                    location_filter=location,
                    total_pages=5,
                    status="pending",
                    triggered_by="scheduled",
                )
                db.add(job)
                await db.flush()
                await manager.submit(job.id)

        await db.commit()
        logger.info("daily_scrape_jobs_created", count=len(sources) * len(locations))


async def daily_report_job() -> None:
    """Generate daily report and optionally email it."""
    logger.info("daily_report_triggered")

    async with async_session() as db:
        svc = ReportService(db)
        report = await svc.generate_report()

        sent = await send_report_email(report)
        if sent:
            report.email_sent = True
            await db.commit()

        logger.info("daily_report_done", date=str(report.report_date), email_sent=sent)


async def proxy_health_job(app_state) -> None:
    """Periodic proxy health check."""
    proxy_pool = getattr(app_state, "proxy_pool", None)
    if proxy_pool:
        await proxy_pool.health_check()


def create_scheduler(app_state) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        daily_scrape_job,
        trigger=CronTrigger(hour=settings.daily_report_hour, minute=settings.daily_report_minute),
        args=[app_state],
        id="daily_scrape",
        name="Daily scrape across all sources and cities",
        replace_existing=True,
    )

    # Generate report 2 hours after scrape starts
    report_hour = (settings.daily_report_hour + 2) % 24
    scheduler.add_job(
        daily_report_job,
        trigger=CronTrigger(hour=report_hour, minute=0),
        id="daily_report",
        name="Daily report generation + email",
        replace_existing=True,
    )

    scheduler.add_job(
        proxy_health_job,
        trigger=IntervalTrigger(minutes=15),
        args=[app_state],
        id="proxy_health",
        name="Proxy pool health check every 15 min",
        replace_existing=True,
    )

    return scheduler
