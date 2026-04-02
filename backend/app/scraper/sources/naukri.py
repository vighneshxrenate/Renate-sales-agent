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

MAX_PAGES_PER_SESSION = 15


@register_scraper
class NaukriScraper(AbstractScraper):
    @property
    def source_name(self) -> str:
        return "naukri"

    async def scrape(
        self,
        job: ScrapeJob,
        browser_pool: BrowserPool,
        proxy_pool: ProxyPool,
    ) -> AsyncGenerator[ScraperResult, None]:
        keywords = (job.keywords or "software engineer").replace(" ", "-")
        location = (job.location_filter or "india").replace(" ", "-").lower()
        max_pages = min(job.total_pages or 5, MAX_PAGES_PER_SESSION)

        proxy = proxy_pool.get_proxy(source="naukri")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="full", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()
            captcha_solver = CaptchaSolver()

            base_url = f"https://www.naukri.com/{quote_plus(keywords)}-jobs-in-{quote_plus(location)}"
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            await source_delay("naukri")

            # Handle Cloudflare challenge if present
            content = await page.content()
            if "cf-challenge" in content.lower() or "challenge-platform" in content.lower():
                if captcha_solver.available:
                    logger.info("naukri_cloudflare_detected")
                    try:
                        site_key = await page.eval_on_selector(
                            "[data-sitekey]", "el => el.getAttribute('data-sitekey')"
                        )
                        token = await captcha_solver.solve_hcaptcha(site_key, page.url)
                        await captcha_solver.inject_solution(page, token)
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        logger.exception("naukri_captcha_failed")
                        return
                else:
                    logger.warning("naukri_cloudflare_no_solver")
                    return

            for page_num in range(1, max_pages + 1):
                html = await page.content()

                yield ScraperResult(
                    raw_html=html,
                    url=page.url,
                    source="naukri",
                    page_number=page_num,
                )

                if page_num < max_pages:
                    next_url = f"{base_url}-{page_num + 1}"
                    await human_scroll(page, scrolls=2)
                    await source_delay("naukri")
                    await page.goto(next_url, wait_until="domcontentloaded", timeout=30000)

            await page.close()
        except Exception:
            logger.exception("naukri_scrape_error")
            if proxy:
                await proxy_pool.report_failure(proxy.server)
            raise
        else:
            if proxy:
                await proxy_pool.report_success(proxy.server, 0)
        finally:
            await browser_pool.release(ctx)
