import uuid as uuid_mod
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.human_behavior import human_scroll, random_delay, random_mouse_move, source_delay
from app.scraper.proxy_pool import ProxyPool

logger = structlog.get_logger()

MAX_REQUESTS_PER_SESSION = 100


@register_scraper
class LinkedInScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "linkedin"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        keywords = quote_plus(job.keywords or "hiring")
        location = quote_plus(job.location_filter or "India")
        max_pages = job.total_pages or 5

        session_id = str(uuid_mod.uuid4())[:8]
        proxy = proxy_pool.get_proxy(source="linkedin", sticky_session=session_id)
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="full", proxy=proxy_dict)

        request_count = 0
        try:
            page = await ctx.context.new_page()

            # Visit LinkedIn homepage first to appear natural
            await page.goto("https://www.linkedin.com", wait_until="domcontentloaded", timeout=30000)
            await random_delay(2, 4)
            await random_mouse_move(page)
            request_count += 1

            # Navigate to jobs search
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await source_delay("linkedin")
            request_count += 1

            for page_num in range(1, max_pages + 1):
                if request_count >= MAX_REQUESTS_PER_SESSION:
                    logger.info("linkedin_session_limit", session=session_id)
                    break

                # Check for login wall or CAPTCHA
                content = await page.content()
                if "authwall" in content.lower() or "captcha" in content.lower():
                    logger.warning("linkedin_blocked", page=page_num, session=session_id)
                    break

                yield ScraperResult(
                    raw_html=content,
                    url=page.url,
                    source="linkedin",
                    page_number=page_num,
                    metadata={"session_id": session_id},
                )

                # Random distraction: occasionally visit a non-job page
                if page_num % 3 == 0:
                    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                    await random_delay(1, 3)
                    await page.go_back(wait_until="domcontentloaded", timeout=15000)
                    request_count += 2

                await human_scroll(page, scrolls=2)
                await random_mouse_move(page)
                await source_delay("linkedin")

                # Paginate
                start = page_num * 25
                next_url = f"{search_url}&start={start}"
                await page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                request_count += 1

            await page.close()
        except Exception:
            logger.exception("linkedin_scrape_error", session=session_id)
            if proxy:
                await proxy_pool.report_failure(proxy.server)
            raise
        else:
            if proxy:
                await proxy_pool.report_success(proxy.server, 0)
        finally:
            await browser_pool.release(ctx)
