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
class IndeedScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "indeed"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        keywords = quote_plus(job.keywords or "software engineer")
        location = quote_plus(job.location_filter or "India")
        max_pages = job.total_pages or 5

        proxy = proxy_pool.get_proxy(source="indeed")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="standard", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()

            for page_num in range(1, max_pages + 1):
                start = (page_num - 1) * 10
                url = f"https://in.indeed.com/jobs?q={keywords}&l={location}&start={start}"

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await source_delay("indeed")
                await human_scroll(page, scrolls=2)

                html = await page.content()

                # Check for CAPTCHA / block page
                if "captcha" in html.lower() or len(html) < 1000:
                    logger.warning("indeed_blocked", page=page_num)
                    break

                yield ScraperResult(
                    raw_html=html,
                    url=page.url,
                    source="indeed",
                    page_number=page_num,
                )

            await page.close()
        except Exception:
            logger.exception("indeed_scrape_error")
            if proxy:
                await proxy_pool.report_failure(proxy.server)
            raise
        else:
            if proxy:
                await proxy_pool.report_success(proxy.server, 0)
        finally:
            await browser_pool.release(ctx)
