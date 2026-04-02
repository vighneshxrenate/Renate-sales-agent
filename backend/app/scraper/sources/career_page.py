from collections.abc import AsyncGenerator
from urllib.parse import urljoin

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.human_behavior import source_delay
from app.scraper.proxy_pool import ProxyPool

logger = structlog.get_logger()

CAREER_PATHS = [
    "/careers", "/jobs", "/work-with-us", "/join-us", "/career",
    "/opportunities", "/hiring", "/openings", "/vacancies",
    "/careers/", "/jobs/", "/work-with-us/",
]


@register_scraper
class CareerPageScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "career_page"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        base_url = job.keywords  # for career_page, keywords holds the company URL
        if not base_url:
            logger.warning("career_page_no_url")
            return

        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        proxy = proxy_pool.get_proxy(source="career_page")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()

            careers_url = await self._find_careers_page(page, base_url)
            if not careers_url:
                logger.info("no_careers_page_found", url=base_url)
                await page.close()
                return

            await page.goto(careers_url, wait_until="domcontentloaded", timeout=30000)
            await source_delay("career_page")

            html = await page.content()
            yield ScraperResult(
                raw_html=html,
                url=careers_url,
                source="career_page",
                page_number=1,
                metadata={"base_url": base_url},
            )

            await page.close()
        except Exception:
            logger.exception("career_page_scrape_error", url=base_url)
            raise
        finally:
            await browser_pool.release(ctx)

    async def _find_careers_page(self, page, base_url: str) -> str | None:
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            return None

        # Check for career links on the main page
        for path in CAREER_PATHS:
            full_url = urljoin(base_url, path)
            try:
                resp = await page.goto(full_url, wait_until="domcontentloaded", timeout=10000)
                if resp and resp.status == 200:
                    return full_url
            except Exception:
                continue

        # Try finding career links in the page content
        try:
            await page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
            links = await page.eval_on_selector_all(
                "a[href]",
                """els => els.map(el => ({href: el.href, text: el.textContent.toLowerCase()}))"""
            )
            career_keywords = ["career", "job", "hiring", "work with us", "join us", "openings"]
            for link in links:
                if any(kw in link.get("text", "") for kw in career_keywords):
                    return link["href"]
        except Exception:
            pass

        return None
