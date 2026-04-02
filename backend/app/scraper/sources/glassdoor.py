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
class GlassdoorScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "glassdoor"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        keywords = quote_plus(job.keywords or "software engineer")
        location = quote_plus(job.location_filter or "India")
        max_pages = job.total_pages or 5

        proxy = proxy_pool.get_proxy(source="glassdoor")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="standard", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()

            base_url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={keywords}&locT=N&locKeyword={location}"
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            await source_delay("glassdoor")

            for page_num in range(1, max_pages + 1):
                await human_scroll(page, scrolls=2)
                html = await page.content()

                if "captcha" in html.lower() or len(html) < 1000:
                    logger.warning("glassdoor_blocked", page=page_num)
                    break

                yield ScraperResult(
                    raw_html=html,
                    url=page.url,
                    source="glassdoor",
                    page_number=page_num,
                )

                if page_num < max_pages:
                    next_btn = page.locator('button[data-test="pagination-next"]')
                    if await next_btn.count() > 0:
                        await next_btn.click()
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)
                        await source_delay("glassdoor")
                    else:
                        break

            await page.close()
        except Exception:
            logger.exception("glassdoor_scrape_error")
            if proxy:
                await proxy_pool.report_failure(proxy.server)
            raise
        else:
            if proxy:
                await proxy_pool.report_success(proxy.server, 0)
        finally:
            await browser_pool.release(ctx)
