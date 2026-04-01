from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import human_scroll, random_delay

logger = structlog.get_logger()

INDEED_URL = "https://www.indeed.com/jobs?q={keywords}&l={location}&start={start}"
INDEED_INDIA_URL = "https://www.indeed.co.in/jobs?q={keywords}&l={location}&start={start}"


class IndeedScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "indeed"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        encoded_keywords = quote_plus(keywords)
        encoded_location = quote_plus(location or "India")
        is_india = self._is_india_location(location)

        session = await self.browser_pool.acquire()
        async with session:
            for page_num in range(max_pages):
                start = page_num * 10
                base_url = INDEED_INDIA_URL if is_india else INDEED_URL
                url = base_url.format(
                    keywords=encoded_keywords,
                    location=encoded_location,
                    start=start,
                )

                logger.info("indeed.scraping_page", page=page_num + 1)
                await self._safe_goto(session.page, url)
                await random_delay(1.5, 3.0)
                await human_scroll(session.page, scrolls=3)

                # Click job cards to load descriptions
                job_cards = await session.page.query_selector_all(
                    "div.job_seen_beacon, td.resultContent, "
                    "div.jobsearch-ResultsList > div"
                )
                for card in job_cards[:15]:
                    try:
                        link = await card.query_selector("a[data-jk], h2 a")
                        if link:
                            await link.click()
                            await random_delay(0.8, 1.5)
                    except Exception:
                        continue

                result = await self._extract_page_html(session.page, page_num + 1)
                yield result

                # Check for next page
                next_link = await session.page.query_selector(
                    "a[data-testid='pagination-page-next'], "
                    "a[aria-label='Next Page']"
                )
                if not next_link:
                    logger.info("indeed.no_more_pages", pages_scraped=page_num + 1)
                    break

                await random_delay(2.0, 4.0)

    def _is_india_location(self, location: str | None) -> bool:
        if not location:
            return True
        india_cities = {"bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "india", "kolkata", "ahmedabad", "noida", "gurgaon", "gurugram"}
        return location.lower().strip() in india_cities
