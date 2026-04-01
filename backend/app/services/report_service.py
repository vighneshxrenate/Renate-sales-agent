from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.report import DailyReport
from app.models.scrape_job import ScrapeJob


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reports(self, page: int, per_page: int) -> tuple[list[DailyReport], int]:
        query = select(DailyReport)
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        query = query.order_by(DailyReport.report_date.desc()).offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_report(self, report_id: UUID) -> DailyReport:
        result = await self.db.execute(select(DailyReport).where(DailyReport.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    async def generate_report(self) -> DailyReport:
        today = date.today()

        existing = (
            await self.db.execute(select(DailyReport).where(DailyReport.report_date == today))
        ).scalar_one_or_none()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        start_of_day = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)

        total_leads = (
            await self.db.execute(
                select(func.count())
                .select_from(Lead)
                .where(Lead.created_at >= start_of_day, Lead.merged_into_id.is_(None))
            )
        ).scalar_one()

        by_source_rows = (
            await self.db.execute(
                select(Lead.source, func.count())
                .where(Lead.created_at >= start_of_day, Lead.merged_into_id.is_(None))
                .group_by(Lead.source)
            )
        ).all()

        by_location_rows = (
            await self.db.execute(
                select(Lead.location, func.count())
                .where(
                    Lead.created_at >= start_of_day,
                    Lead.merged_into_id.is_(None),
                    Lead.location.is_not(None),
                )
                .group_by(Lead.location)
            )
        ).all()

        jobs_today = (
            await self.db.execute(
                select(ScrapeJob).where(ScrapeJob.created_at >= start_of_day)
            )
        ).scalars().all()

        report = DailyReport(
            report_date=today,
            total_leads_found=total_leads,
            new_leads=total_leads,
            leads_by_source={row[0]: row[1] for row in by_source_rows},
            leads_by_location={row[0] or "Unknown": row[1] for row in by_location_rows},
            top_hiring_positions=[],
            scrape_jobs_run=len(jobs_today),
            scrape_jobs_failed=sum(1 for j in jobs_today if j.status == "failed"),
        )
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report
