from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: UUID
    report_date: date
    total_leads_found: int
    new_leads: int
    leads_by_source: dict[str, Any]
    leads_by_location: dict[str, Any]
    top_hiring_positions: list[dict[str, Any]]
    scrape_jobs_run: int
    scrape_jobs_failed: int
    email_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    reports: list[ReportOut]
    total: int
    page: int
    per_page: int
