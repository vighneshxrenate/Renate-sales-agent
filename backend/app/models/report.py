import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_date: Mapped[date] = mapped_column(Date, unique=True)
    total_leads_found: Mapped[int] = mapped_column(Integer, default=0)
    new_leads: Mapped[int] = mapped_column(Integer, default=0)
    leads_by_source: Mapped[dict] = mapped_column(JSONB, default=dict)
    leads_by_location: Mapped[dict] = mapped_column(JSONB, default=dict)
    top_hiring_positions: Mapped[list] = mapped_column(JSONB, default=list)
    scrape_jobs_run: Mapped[int] = mapped_column(Integer, default=0)
    scrape_jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
