from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.human_behavior import human_scroll, source_delay
from app.scraper.proxy_pool import ProxyPool

logger = structlog.get_logger()


@register_scraper
class GoogleJobsScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "google_jobs"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        keywords = quote_plus(job.keywords or "software engineer")
        location = quote_plus(job.location_filter or "India")
        max_pages = job.total_pages or 5

        proxy = proxy_pool.get_proxy(source="google_jobs")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="minimal", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()
            url = f"https://www.google.com/search?q={keywords}+jobs+in+{location}&ibp=htl;jobs"

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await source_delay("google_jobs")

            for page_num in range(1, max_pages + 1):
                html = await page.content()
                yield ScraperResult(
                    raw_html=html,
                    url=page.url,
                    source="google_jobs",
                    page_number=page_num,
                )

                await human_scroll(page, scrolls=3)
                await source_delay("google_jobs")

                # Google Jobs loads more via scroll; check if new content appeared
                new_html = await page.content()
                if len(new_html) == len(html):
                    break

            await page.close()
        except Exception:
            logger.exception("google_jobs_scrape_error")
            raise
        finally:
            await browser_pool.release(ctx)
