from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.scraper.browser_pool import BrowserPool
from app.scraper.captcha_solver import CaptchaSolver
from app.scraper.manager import ScraperJobManager
from app.scraper.proxy_pool import ProxyPool

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up")

    proxy_pool = ProxyPool()
    await proxy_pool.initialize()

    browser_pool = BrowserPool(
        proxy_pool, settings.playwright_ws_endpoint, settings.browser_pool_size
    )
    await browser_pool.initialize()

    captcha_solver = CaptchaSolver(settings.captcha_api_key)

    scraper_manager = ScraperJobManager(browser_pool, proxy_pool, captcha_solver)
    await scraper_manager.start()

    app.state.proxy_pool = proxy_pool
    app.state.browser_pool = browser_pool
    app.state.captcha_solver = captcha_solver
    app.state.scraper_manager = scraper_manager

    yield

    logger.info("shutting down")
    await scraper_manager.stop()
    await captcha_solver.close()
    await browser_pool.close()


app = FastAPI(title="Renate Sales Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
