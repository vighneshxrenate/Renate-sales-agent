from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.logging_config import setup_logging
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.scheduler.jobs import create_scheduler
from app.scraper.browser_pool import BrowserPool
from app.scraper.manager import ScraperJobManager
from app.scraper.proxy_pool import ProxyPool

setup_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up")

    proxy_pool = ProxyPool()
    await proxy_pool.initialize()
    app.state.proxy_pool = proxy_pool

    browser_pool = BrowserPool()
    try:
        await browser_pool.initialize()
    except Exception:
        logger.warning("browser_pool_init_failed — scraping will be unavailable")
        browser_pool = None
    app.state.browser_pool = browser_pool

    if browser_pool:
        manager = ScraperJobManager(browser_pool, proxy_pool)
        await manager.start()
        app.state.scraper_manager = manager
    else:
        app.state.scraper_manager = None

    scheduler = create_scheduler(app.state)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info("scheduler_started")

    yield

    app.state.scheduler.shutdown(wait=False)
    if app.state.scraper_manager:
        await app.state.scraper_manager.stop()
    if app.state.browser_pool:
        await app.state.browser_pool.close()

    logger.info("shutting down")


app = FastAPI(title="Renate Sales Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Import scraper sources to trigger registration
import app.scraper.sources.google_jobs  # noqa: F401, E402
import app.scraper.sources.career_page  # noqa: F401, E402
import app.scraper.sources.linkedin  # noqa: F401, E402
import app.scraper.sources.naukri  # noqa: F401, E402
import app.scraper.sources.indeed  # noqa: F401, E402
import app.scraper.sources.glassdoor  # noqa: F401, E402
