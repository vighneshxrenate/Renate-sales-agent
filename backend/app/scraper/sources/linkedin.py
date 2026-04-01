from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import (
    human_scroll,
    random_delay,
    random_distraction,
)

logger = structlog.get_logger()

LINKEDIN_JOBS_URL = "https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&start={start}"
MAX_REQUESTS_PER_SESSION = 100
LINKEDIN_LOCATIONS = {
    "bangalore": "Bengaluru%2C+Karnataka%2C+India",
    "bengaluru": "Bengaluru%2C+Karnataka%2C+India",
    "mumbai": "Mumbai%2C+Maharashtra%2C+India",
    "delhi": "New+Delhi%2C+Delhi%2C+India",
    "hyderabad": "Hyderabad%2C+Telangana%2C+India",
    "pune": "Pune%2C+Maharashtra%2C+India",
    "chennai": "Chennai%2C+Tamil+Nadu%2C+India",
    "india": "India",
}


class LinkedInScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "linkedin"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        encoded_keywords = quote_plus(keywords)
        encoded_location = self._resolve_location(location)

        session = await self.browser_pool.acquire()
        async with session:
            requests_made = 0

            for page_num in range(max_pages):
                if requests_made >= MAX_REQUESTS_PER_SESSION:
                    logger.info("linkedin.session_limit_reached", requests=requests_made)
                    break

                start = page_num * 25
                url = LINKEDIN_JOBS_URL.format(
                    keywords=encoded_keywords,
                    location=encoded_location,
                    start=start,
                )

                logger.info("linkedin.scraping_page", page=page_num + 1)

                # Pre-navigation delay (mimic human browsing)
                if page_num > 0:
                    await random_delay(3.0, 6.0)
                    if page_num % 3 == 0:
                        await random_distraction(session.page)

                await self._safe_goto(session.page, url, timeout=45000)
                requests_made += 1
                await random_delay(2.0, 4.0)

                # Check for auth wall
                if await self._is_auth_wall(session.page):
                    logger.warning("linkedin.auth_wall_detected", page=page_num + 1)
                    break

                # Scroll to load all job cards
                await human_scroll(session.page, scrolls=5)
                await random_delay(1.0, 2.0)

                # Click individual job cards to load detail pane
                job_cards = await session.page.query_selector_all(
                    "div.base-card, li.jobs-search-results__list-item, "
                    "div.job-search-card"
                )
                for i, card in enumerate(job_cards[:15]):
                    try:
                        await card.click()
                        await random_delay(1.0, 2.5)
                        requests_made += 1
                    except Exception:
                        continue

                result = await self._extract_page_html(session.page, page_num + 1)
                yield result

                # Check for "no more results"
                no_results = await session.page.query_selector(
                    "div.no-results, p:has-text('No matching jobs')"
                )
                if no_results:
                    logger.info("linkedin.no_more_results", pages_scraped=page_num + 1)
                    break

    def _resolve_location(self, location: str | None) -> str:
        if not location:
            return LINKEDIN_LOCATIONS["india"]
        key = location.lower().strip()
        return LINKEDIN_LOCATIONS.get(key, quote_plus(location))

    async def _is_auth_wall(self, page) -> bool:
        auth_indicators = await page.query_selector(
            "form.login__form, div.authwall, "
            "input[name='session_key'], "
            "h1:has-text('Sign in')"
        )
        return auth_indicators is not None
