from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class LeadEmailOut(BaseModel):
    id: UUID
    email: str
    email_type: str | None
    source: str | None
    verified: bool

    model_config = {"from_attributes": True}


class LeadPhoneOut(BaseModel):
    id: UUID
    phone: str
    phone_type: str | None

    model_config = {"from_attributes": True}


class HiringPositionOut(BaseModel):
    id: UUID
    title: str
    department: str | None
    location: str | None
    job_type: str | None
    experience_level: str | None
    salary_range: str | None
    posted_date: datetime | None
    source_url: str | None

    model_config = {"from_attributes": True}


class LeadOut(BaseModel):
    id: UUID
    company_name: str
    location: str | None
    website: str | None
    industry: str | None
    company_size: str | None
    description: str | None
    source: str
    source_url: str
    confidence_score: float | None
    status: str
    created_at: datetime
    updated_at: datetime
    emails: list[LeadEmailOut] = []
    phones: list[LeadPhoneOut] = []
    positions: list[HiringPositionOut] = []

    model_config = {"from_attributes": True}


class LeadCreate(BaseModel):
    company_name: str
    location: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    description: str | None = None
    source: str
    source_url: str
    confidence_score: float | None = None


class LeadUpdate(BaseModel):
    status: str | None = None
    company_name: str | None = None
    location: str | None = None
    website: str | None = None
    industry: str | None = None


class LeadListResponse(BaseModel):
    leads: list[LeadOut]
    total: int
    page: int
    per_page: int
