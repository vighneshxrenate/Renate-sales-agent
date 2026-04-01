from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field

import structlog

from app.scraper.browser_pool import BrowserPool
from app.scraper.captcha_solver import CaptchaSolver
from app.scraper.human_behavior import random_delay

logger = structlog.get_logger()


@dataclass
class ScraperResult:
    raw_html: str
    source_url: str
    source_name: str
    page_number: int
    metadata: dict = field(default_factory=dict)


class BaseScraper(ABC):
    def __init__(self, browser_pool: BrowserPool, captcha_solver: CaptchaSolver):
        self.browser_pool = browser_pool
        self.captcha_solver = captcha_solver

    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]: ...

    async def _safe_goto(self, page, url: str, timeout: int = 30000) -> None:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception:
            logger.warning("scraper.goto_retry", url=url)
            await random_delay(2.0, 5.0)
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

        await self.captcha_solver.solve_if_present(page)

    async def _extract_page_html(self, page, page_number: int) -> ScraperResult:
        html = await page.content()
        return ScraperResult(
            raw_html=html,
            source_url=page.url,
            source_name=self.source_name,
            page_number=page_number,
        )
