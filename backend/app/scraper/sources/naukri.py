from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import human_scroll, random_delay

logger = structlog.get_logger()

NAUKRI_JOBS_URL = "https://www.naukri.com/{keywords}-jobs-in-{location}?k={keywords_raw}&l={location_raw}&nignbevent_src=jobsearchDeskGNB&experience=&pageNo={page}"
NAUKRI_SEARCH_URL = "https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword&searchType=adv&keyword={keywords}&location={location}&pageNo={page}"

NAUKRI_LOCATIONS = {
    "bangalore": "bangalore",
    "bengaluru": "bangalore",
    "mumbai": "mumbai",
    "delhi": "delhi%2Fncr",
    "hyderabad": "hyderabad",
    "pune": "pune",
    "chennai": "chennai",
}


class NaukriScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "naukri"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        location_slug = self._resolve_location(location)
        keywords_slug = keywords.lower().replace(" ", "-")
        keywords_raw = quote_plus(keywords)
        location_raw = quote_plus(location or "india")

        session = await self.browser_pool.acquire()
        async with session:
            for page_num in range(1, max_pages + 1):
                url = NAUKRI_JOBS_URL.format(
                    keywords=keywords_slug,
                    location=location_slug,
                    keywords_raw=keywords_raw,
                    location_raw=location_raw,
                    page=page_num,
                )

                logger.info("naukri.scraping_page", page=page_num, url=url)
                await self._safe_goto(session.page, url, timeout=40000)
                await random_delay(3.0, 6.0)

                # Check for Cloudflare challenge
                if await self._is_cloudflare_challenge(session.page):
                    logger.warning("naukri.cloudflare_detected", page=page_num)
                    await random_delay(5.0, 10.0)
                    # Wait for challenge to resolve
                    try:
                        await session.page.wait_for_selector(
                            "div.srp-jobtuple-wrapper, article.jobTuple",
                            timeout=30000,
                        )
                    except Exception:
                        logger.error("naukri.cloudflare_blocked")
                        session.mark_failed()
                        break

                await human_scroll(session.page, scrolls=4)
                await random_delay(1.0, 2.0)

                # Click job cards to load details
                job_cards = await session.page.query_selector_all(
                    "article.jobTuple, div.srp-jobtuple-wrapper, "
                    "div.cust-job-tuple"
                )
                for card in job_cards[:15]:
                    try:
                        await card.click()
                        await random_delay(1.0, 2.0)
                    except Exception:
                        continue

                result = await self._extract_page_html(session.page, page_num)
                yield result

                # Check if there are more pages
                no_results = await session.page.query_selector(
                    "div.no-result, div:has-text('No matching results')"
                )
                if no_results:
                    logger.info("naukri.no_more_results", pages_scraped=page_num)
                    break

                await random_delay(3.0, 6.0)

    def _resolve_location(self, location: str | None) -> str:
        if not location:
            return "india"
        key = location.lower().strip()
        return NAUKRI_LOCATIONS.get(key, location.lower().replace(" ", "-"))

    async def _is_cloudflare_challenge(self, page) -> bool:
        cf_indicators = await page.query_selector(
            "#challenge-running, #cf-challenge-running, "
            "div.cf-browser-verification, "
            "div[id*='challenge-form']"
        )
        return cf_indicators is not None
