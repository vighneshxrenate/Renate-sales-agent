from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import human_scroll, random_delay

logger = structlog.get_logger()

GOOGLE_JOBS_URL = "https://www.google.com/search?q={query}&ibp=htl;jobs&start={start}"


class GoogleJobsScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "google_jobs"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        query = keywords
        if location:
            query = f"{keywords} jobs in {location}"
        else:
            query = f"{keywords} jobs in India"

        encoded_query = quote_plus(query)

        session = await self.browser_pool.acquire()
        async with session:
            for page_num in range(max_pages):
                start = page_num * 10
                url = GOOGLE_JOBS_URL.format(query=encoded_query, start=start)

                logger.info("google_jobs.scraping_page", page=page_num + 1, url=url)
                await self._safe_goto(session.page, url)
                await random_delay(2.0, 4.0)

                # Scroll to load lazy content
                await human_scroll(session.page, scrolls=3)
                await random_delay(1.0, 2.0)

                # Expand job cards by clicking them to get full details
                job_cards = await session.page.query_selector_all(
                    "li.iFjolb, div.PwjeAc, div[jscontroller] div[data-ved]"
                )
                for i, card in enumerate(job_cards[:10]):
                    try:
                        await card.click()
                        await random_delay(0.8, 1.5)
                    except Exception:
                        continue

                result = await self._extract_page_html(session.page, page_num + 1)
                yield result

                # Check if there are more results
                next_btn = await session.page.query_selector(
                    "div[aria-label='Next'] , span:has-text('Next')"
                )
                if not next_btn and page_num > 0:
                    logger.info("google_jobs.no_more_pages", pages_scraped=page_num + 1)
                    break

                await random_delay(2.0, 5.0)
