from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.scrape_job import ScrapeJobCreate, ScrapeJobOut, ScrapeJobListResponse
from app.services.job_service import JobService

router = APIRouter()


@router.post("", response_model=ScrapeJobOut, status_code=201)
async def trigger_job(data: ScrapeJobCreate, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    return await svc.create_job(data)


@router.get("", response_model=ScrapeJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = JobService(db)
    jobs, total = await svc.list_jobs(page=page, per_page=per_page, status=status)
    return ScrapeJobListResponse(jobs=jobs, total=total, page=page, per_page=per_page)


@router.get("/{job_id}", response_model=ScrapeJobOut)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    return await svc.get_job(job_id)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = JobService(db)
    await svc.cancel_job(job_id)
    return {"ok": True}
