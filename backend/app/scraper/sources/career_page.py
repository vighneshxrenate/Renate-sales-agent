from collections.abc import AsyncGenerator

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import human_scroll, random_delay

logger = structlog.get_logger()

CAREER_PATH_PATTERNS = [
    "/careers", "/jobs", "/join-us", "/work-with-us",
    "/about/careers", "/company/careers", "/en/careers",
]


class CareerPageScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "career_page"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        """Scrape career pages from URLs passed in keywords (comma-separated company URLs)."""
        urls = [u.strip() for u in keywords.split(",") if u.strip()]

        for i, base_url in enumerate(urls):
            if i >= max_pages:
                break

            session = await self.browser_pool.acquire()
            async with session:
                career_url = await self._find_career_page(session.page, base_url)
                if not career_url:
                    logger.info("career_page.no_careers_found", url=base_url)
                    continue

                logger.info("career_page.scraping", url=career_url)
                await self._safe_goto(session.page, career_url)
                await random_delay(1.5, 3.0)
                await human_scroll(session.page, scrolls=3)

                result = await self._extract_page_html(session.page, i + 1)
                result.metadata["base_url"] = base_url
                yield result

                # Also scrape /about and /contact for enrichment
                for path in ["/about", "/about-us", "/contact", "/contact-us"]:
                    try:
                        enrich_url = base_url.rstrip("/") + path
                        await self._safe_goto(session.page, enrich_url, timeout=15000)
                        await random_delay(1.0, 2.0)
                        enrich_result = await self._extract_page_html(session.page, i + 1)
                        enrich_result.metadata["enrichment_page"] = path
                        enrich_result.metadata["base_url"] = base_url
                        yield enrich_result
                    except Exception:
                        continue

    async def _find_career_page(self, page, base_url: str) -> str | None:
        # First try the base URL itself if it looks like a career page
        lower_url = base_url.lower()
        if any(p in lower_url for p in ["/career", "/jobs", "/join", "/hiring"]):
            return base_url

        # Try common career paths
        for path in CAREER_PATH_PATTERNS:
            career_url = base_url.rstrip("/") + path
            try:
                response = await page.goto(career_url, wait_until="domcontentloaded", timeout=10000)
                if response and response.ok:
                    return career_url
            except Exception:
                continue

        # Fall back to base URL and look for career links
        try:
            await self._safe_goto(page, base_url)
            await random_delay(1.0, 2.0)
            career_link = await page.query_selector(
                "a[href*='career'], a[href*='jobs'], a[href*='join'], "
                "a:has-text('Careers'), a:has-text('Jobs'), a:has-text('Join Us')"
            )
            if career_link:
                href = await career_link.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        return base_url.rstrip("/") + href
                    return href
        except Exception:
            pass

        return None
