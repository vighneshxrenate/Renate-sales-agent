from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.lead import LeadCreate, LeadOut, LeadUpdate, LeadListResponse
from app.services.lead_service import LeadService

router = APIRouter()


@router.get("", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    source: str | None = None,
    status: str | None = None,
    location: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    svc = LeadService(db)
    leads, total = await svc.list_leads(
        page=page,
        per_page=per_page,
        search=search,
        source=source,
        status=status,
        location=location,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return LeadListResponse(leads=leads, total=total, page=page, per_page=per_page)


@router.get("/stats")
async def lead_stats(db: AsyncSession = Depends(get_db)):
    svc = LeadService(db)
    return await svc.get_stats()


@router.get("/export")
async def export_leads(
    source: str | None = None,
    status: str | None = None,
    location: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    svc = LeadService(db)
    return await svc.export_csv(source=source, status=status, location=location)


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = LeadService(db)
    return await svc.get_lead(lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: UUID, data: LeadUpdate, db: AsyncSession = Depends(get_db)):
    svc = LeadService(db)
    return await svc.update_lead(lead_id, data)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    svc = LeadService(db)
    await svc.delete_lead(lead_id)
    return {"ok": True}
