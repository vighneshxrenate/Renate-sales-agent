from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.report import ReportOut, ReportListResponse
from app.services.report_service import ReportService

router = APIRouter()


@router.get("", response_model=ReportListResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = ReportService(db)
    reports, total = await svc.list_reports(page=page, per_page=per_page)
    return ReportListResponse(reports=reports, total=total, page=page, per_page=per_page)


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = ReportService(db)
    return await svc.get_report(report_id)


@router.post("/generate", response_model=ReportOut, status_code=201)
async def generate_report(db: AsyncSession = Depends(get_db)):
    svc = ReportService(db)
    return await svc.generate_report()
