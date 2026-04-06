import asyncio
import random
from dataclasses import dataclass, field

import structlog
from playwright.async_api import Browser, BrowserContext, async_playwright

from app.config import settings
from app.scraper.stealth import apply_stealth

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

LOCALES = ["en-US", "en-IN", "en-GB"]
TIMEZONES = ["Asia/Kolkata", "America/New_York", "Europe/London"]

MAX_REQUESTS_PER_CONTEXT = 100


@dataclass
class ContextWrapper:
    context: BrowserContext
    request_count: int = 0
    stealth_level: str = "full"
    id: str = field(default_factory=lambda: f"ctx-{random.randint(1000, 9999)}")


class BrowserPool:
    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._playwright = None
        self._available: asyncio.Queue[ContextWrapper] = asyncio.Queue()
        self._all_contexts: list[ContextWrapper] = []
        self._lock = asyncio.Lock()
        self._pool_size = settings.browser_pool_size

    async def initialize(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.connect(
            settings.playwright_ws_endpoint
        )
        logger.info("browser_pool_initialized", endpoint=settings.playwright_ws_endpoint)

    async def _create_context(
        self, stealth_level: str = "full", proxy: dict | None = None
    ) -> ContextWrapper:
        if not self._browser:
            raise RuntimeError("BrowserPool not initialized")

        ua = random.choice(USER_AGENTS)
        viewport = random.choice(VIEWPORTS)
        locale = random.choice(LOCALES)
        tz = random.choice(TIMEZONES)

        opts: dict = {
            "user_agent": ua,
            "viewport": viewport,
            "locale": locale,
            "timezone_id": tz,
            "java_script_enabled": True,
            "ignore_https_errors": True,
        }
        if proxy:
            opts["proxy"] = proxy

        context = await self._browser.new_context(**opts)
        wrapper = ContextWrapper(context=context, stealth_level=stealth_level)

        page = await context.new_page()
        await apply_stealth(page, stealth_level)
        await page.close()

        self._all_contexts.append(wrapper)
        logger.debug("browser_context_created", id=wrapper.id, stealth=stealth_level)
        return wrapper

    async def acquire(
        self, stealth_level: str = "full", proxy: dict | None = None
    ) -> ContextWrapper:
        async with self._lock:
            while not self._available.empty():
                wrapper = await self._available.get()
                if wrapper.request_count < MAX_REQUESTS_PER_CONTEXT:
                    wrapper.request_count += 1
                    return wrapper
                await wrapper.context.close()
                self._all_contexts.remove(wrapper)

            wrapper = await self._create_context(stealth_level, proxy)
            wrapper.request_count = 1
            return wrapper

    async def release(self, wrapper: ContextWrapper) -> None:
        if wrapper.request_count >= MAX_REQUESTS_PER_CONTEXT:
            await wrapper.context.close()
            if wrapper in self._all_contexts:
                self._all_contexts.remove(wrapper)
            logger.debug("browser_context_retired", id=wrapper.id)
        else:
            await self._available.put(wrapper)

    async def close(self) -> None:
        for wrapper in self._all_contexts:
            try:
                await wrapper.context.close()
            except Exception:
                pass
        self._all_contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("browser_pool_closed")
