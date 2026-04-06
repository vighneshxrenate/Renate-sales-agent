import asyncio
import re
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.captcha_solver import CaptchaSolver
from app.scraper.human_behavior import human_scroll, source_delay
from app.scraper.proxy_pool import ProxyPool

logger = structlog.get_logger()

GOOGLE_CONSENT_COOKIES = [
    {"name": "CONSENT", "value": "YES+cb.20231008-07-p0.en+FX+410", "domain": ".google.co.in", "path": "/"},
    {"name": "CONSENT", "value": "YES+cb.20231008-07-p0.en+FX+410", "domain": ".google.com", "path": "/"},
]


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
        max_pages = job.total_pages or 3

        # Try without proxy first (direct IP is less likely to be flagged)
        # Fall back to proxy if direct fails
        proxy = proxy_pool.get_proxy(source="google_jobs")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="full", proxy=None)
        captcha_solver = CaptchaSolver()

        try:
            # Pre-set consent cookies to bypass consent screen
            for cookie in GOOGLE_CONSENT_COOKIES:
                await ctx.context.add_cookies([cookie])

            page = await ctx.context.new_page()
            url = f"https://www.google.co.in/search?q={keywords}+jobs+in+{location}&ibp=htl;jobs&hl=en"

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # Check for CAPTCHA/block
            content = await page.content()
            page_text = await page.inner_text("body")

            if "unusual traffic" in page_text.lower():
                logger.warning("google_jobs_captcha_detected")
                resolved = await self._handle_captcha(page, content, captcha_solver)
                if not resolved:
                    logger.error("google_jobs_captcha_unresolved")
                    return
                await page.wait_for_timeout(3000)

            for page_num in range(1, max_pages + 1):
                html = await page.content()
                page_text = await page.inner_text("body")

                if "unusual traffic" in page_text.lower():
                    logger.warning("google_jobs_blocked_on_page", page=page_num)
                    break

                if len(page_text.strip()) < 100:
                    logger.warning("google_jobs_empty_page", page=page_num)
                    break

                yield ScraperResult(
                    raw_html=html,
                    url=page.url,
                    source="google_jobs",
                    page_number=page_num,
                )

                if page_num < max_pages:
                    # Scroll to load more jobs
                    await human_scroll(page, scrolls=5)
                    await source_delay("google_jobs")

                    # Google Jobs loads more via scroll (infinite scroll)
                    new_html = await page.content()
                    if len(new_html) == len(html):
                        logger.info("google_jobs_no_more_results", page=page_num)
                        break

            await page.close()
        except Exception:
            logger.exception("google_jobs_scrape_error")
            raise
        finally:
            await browser_pool.release(ctx)

    async def _handle_captcha(self, page, content: str, solver: CaptchaSolver) -> bool:
        if not solver.available:
            logger.warning("google_jobs_captcha_no_solver")
            return False

        sitekeys = re.findall(r'data-sitekey="([^"]+)"', content)
        if not sitekeys:
            logger.warning("google_jobs_no_sitekey_found")
            return False

        site_key = sitekeys[0]
        try:
            token = await solver.solve_recaptcha(site_key, page.url)
            await solver.inject_solution(page, token)
            # Submit the form
            submit_btn = await page.query_selector("#recaptcha-verify-button, button[type=submit]")
            if submit_btn:
                await submit_btn.click()
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)

            text = await page.inner_text("body")
            if "unusual traffic" not in text.lower():
                logger.info("google_jobs_captcha_solved")
                return True
        except Exception:
            logger.exception("google_jobs_captcha_solve_failed")

        return False
