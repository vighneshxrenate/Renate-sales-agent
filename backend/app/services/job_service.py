from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scrape_job import ScrapeJob
from app.schemas.scrape_job import ScrapeJobCreate

if TYPE_CHECKING:
    from app.scraper.manager import ScraperJobManager


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, data: ScrapeJobCreate, manager: ScraperJobManager) -> ScrapeJob:
        if not manager.has_scraper(data.source):
            available = manager.registered_sources
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source '{data.source}'. Available: {available}",
            )

        job = ScrapeJob(
            source=data.source,
            keywords=data.keywords,
            location_filter=data.location_filter,
            total_pages=data.max_pages,
            status="pending",
            triggered_by="manual",
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        await manager.submit(
            job_id=job.id,
            source=job.source,
            keywords=job.keywords or "",
            location=job.location_filter,
            max_pages=job.total_pages or 10,
        )
        return job

    async def list_jobs(
        self, page: int, per_page: int, status: str | None = None
    ) -> tuple[list[ScrapeJob], int]:
        query = select(ScrapeJob)
        if status:
            query = query.where(ScrapeJob.status == status)

        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()

        query = query.order_by(ScrapeJob.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_job(self, job_id: UUID) -> ScrapeJob:
        result = await self.db.execute(select(ScrapeJob).where(ScrapeJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def cancel_job(self, job_id: UUID, manager: ScraperJobManager) -> None:
        job = await self.get_job(job_id)
        if job.status not in ("pending", "running"):
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        job.status = "cancelled"
        await self.db.commit()
        await manager.cancel(job_id)
