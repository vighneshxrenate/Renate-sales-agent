from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ScrapeJobCreate(BaseModel):
    source: str
    keywords: str
    location_filter: str | None = None
    max_pages: int = 10


class ScrapeJobOut(BaseModel):
    id: UUID
    source: str
    keywords: str | None
    location_filter: str | None
    status: str
    triggered_by: str
    total_pages: int | None
    pages_scraped: int
    leads_found: int
    leads_new: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScrapeJobListResponse(BaseModel):
    jobs: list[ScrapeJobOut]
    total: int
    page: int
    per_page: int
