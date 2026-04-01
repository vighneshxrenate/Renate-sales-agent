import csv
import io
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead, LeadEmail, LeadPhone
from app.models.job_position import HiringPosition
from app.schemas.lead import LeadUpdate


class LeadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_leads(
        self,
        page: int,
        per_page: int,
        search: str | None = None,
        source: str | None = None,
        status: str | None = None,
        location: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Lead], int]:
        query = select(Lead).where(Lead.merged_into_id.is_(None))

        if search:
            query = query.where(Lead.company_name.ilike(f"%{search}%"))
        if source:
            query = query.where(Lead.source == source)
        if status:
            query = query.where(Lead.status == status)
        if location:
            query = query.where(Lead.location.ilike(f"%{location}%"))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        sort_col = getattr(Lead, sort_by, Lead.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        query = (
            query.offset((page - 1) * per_page)
            .limit(per_page)
            .options(
                selectinload(Lead.emails),
                selectinload(Lead.phones),
                selectinload(Lead.positions),
            )
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_lead(self, lead_id: UUID) -> Lead:
        query = (
            select(Lead)
            .where(Lead.id == lead_id)
            .options(
                selectinload(Lead.emails),
                selectinload(Lead.phones),
                selectinload(Lead.positions),
            )
        )
        result = await self.db.execute(query)
        lead = result.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return lead

    async def update_lead(self, lead_id: UUID, data: LeadUpdate) -> Lead:
        lead = await self.get_lead(lead_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(lead, field, value)
        await self.db.commit()
        await self.db.refresh(lead)
        return lead

    async def delete_lead(self, lead_id: UUID) -> None:
        lead = await self.get_lead(lead_id)
        await self.db.delete(lead)
        await self.db.commit()

    async def get_stats(self) -> dict:
        base = select(Lead).where(Lead.merged_into_id.is_(None))

        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

        by_source = (
            await self.db.execute(
                select(Lead.source, func.count())
                .where(Lead.merged_into_id.is_(None))
                .group_by(Lead.source)
            )
        ).all()

        by_status = (
            await self.db.execute(
                select(Lead.status, func.count())
                .where(Lead.merged_into_id.is_(None))
                .group_by(Lead.status)
            )
        ).all()

        return {
            "total": total,
            "by_source": {row[0]: row[1] for row in by_source},
            "by_status": {row[0]: row[1] for row in by_status},
        }

    async def export_csv(
        self,
        source: str | None = None,
        status: str | None = None,
        location: str | None = None,
    ) -> StreamingResponse:
        query = (
            select(Lead)
            .where(Lead.merged_into_id.is_(None))
            .options(selectinload(Lead.emails), selectinload(Lead.phones))
        )
        if source:
            query = query.where(Lead.source == source)
        if status:
            query = query.where(Lead.status == status)
        if location:
            query = query.where(Lead.location.ilike(f"%{location}%"))

        result = await self.db.execute(query)
        leads = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Company Name", "Location", "Website", "Industry", "Company Size",
            "Source", "Source URL", "Status", "Emails", "Phones", "Created At",
        ])
        for lead in leads:
            emails = "; ".join(e.email for e in lead.emails)
            phones = "; ".join(p.phone for p in lead.phones)
            writer.writerow([
                lead.company_name, lead.location, lead.website, lead.industry,
                lead.company_size, lead.source, lead.source_url, lead.status,
                emails, phones, lead.created_at.isoformat(),
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads.csv"},
        )
