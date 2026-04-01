from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.leads import router as leads_router
from app.api.reports import router as reports_router
from app.api.scrape_jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(leads_router, prefix="/leads", tags=["leads"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(reports_router, prefix="/reports", tags=["reports"])
