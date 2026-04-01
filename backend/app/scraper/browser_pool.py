import asyncio
import random

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.scraper.proxy_pool import ProxyEntry, ProxyPool
from app.scraper.stealth import apply_stealth

logger = structlog.get_logger()

FINGERPRINTS = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-US",
        "timezone_id": "America/Los_Angeles",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "viewport": {"width": 1680, "height": 1050},
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-US",
        "timezone_id": "America/Chicago",
    },
    {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "viewport": {"width": 1536, "height": 864},
        "locale": "en-US",
        "timezone_id": "America/New_York",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "viewport": {"width": 2560, "height": 1440},
        "locale": "en-GB",
        "timezone_id": "Europe/London",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "viewport": {"width": 1280, "height": 720},
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {"width": 1440, "height": 900},
        "locale": "en-IN",
        "timezone_id": "Asia/Kolkata",
    },
]


class BrowserPool:
    def __init__(self, proxy_pool: ProxyPool, ws_endpoint: str, pool_size: int = 5):
        self._proxy_pool = proxy_pool
        self._ws_endpoint = ws_endpoint
        self._semaphore = asyncio.Semaphore(pool_size)
        self._playwright = None
        self._browser: Browser | None = None

    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect(self._ws_endpoint)
        logger.info("browser_pool.connected", endpoint=self._ws_endpoint)

    async def acquire(self):
        await self._semaphore.acquire()
        context: BrowserContext | None = None
        proxy_entry: ProxyEntry | None = None
        try:
            fingerprint = random.choice(FINGERPRINTS)
            proxy_entry = await self._proxy_pool.get_proxy()

            context_opts = {
                "user_agent": fingerprint["user_agent"],
                "viewport": fingerprint["viewport"],
                "locale": fingerprint["locale"],
                "timezone_id": fingerprint["timezone_id"],
            }
            if proxy_entry:
                context_opts["proxy"] = {"server": proxy_entry.url}

            context = await self._browser.new_context(**context_opts)
            page = await context.new_page()
            await apply_stealth(page)

            return _BrowserSession(
                context=context,
                page=page,
                proxy_entry=proxy_entry,
                pool=self,
            )
        except Exception:
            if context:
                await context.close()
            self._semaphore.release()
            raise

    async def _release(self, session: "_BrowserSession", failed: bool = False) -> None:
        try:
            await session.context.close()
        except Exception:
            pass
        self._semaphore.release()

        if session.proxy_entry:
            if failed:
                await self._proxy_pool.report_failure(session.proxy_entry)
            else:
                await self._proxy_pool.report_success(session.proxy_entry)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("browser_pool.closed")


class _BrowserSession:
    def __init__(
        self,
        context: BrowserContext,
        page: Page,
        proxy_entry: ProxyEntry | None,
        pool: BrowserPool,
    ):
        self.context = context
        self.page = page
        self.proxy_entry = proxy_entry
        self._pool = pool
        self._failed = False

    def mark_failed(self) -> None:
        self._failed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._failed = True
        await self._pool._release(self, failed=self._failed)
        return False
