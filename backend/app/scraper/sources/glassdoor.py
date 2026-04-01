from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.scraper.base import BaseScraper, ScraperResult
from app.scraper.human_behavior import human_scroll, random_delay

logger = structlog.get_logger()

GLASSDOOR_URL = "https://www.glassdoor.co.in/Job/india-{keywords}-jobs-SRCH_IL.0,5_IN115_KO6,{keyword_end}.htm?p={page}"


class GlassdoorScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "glassdoor"

    async def scrape(
        self, keywords: str, location: str | None, max_pages: int
    ) -> AsyncGenerator[ScraperResult, None]:
        session = await self.browser_pool.acquire()
        async with session:
            # Glassdoor URL structure is complex, use search page
            search_url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={quote_plus(keywords)}"
            if location:
                search_url += f"&locT=C&locKeyword={quote_plus(location)}"

            for page_num in range(1, max_pages + 1):
                page_url = f"{search_url}&p={page_num}" if page_num > 1 else search_url

                logger.info("glassdoor.scraping_page", page=page_num)
                await self._safe_goto(session.page, page_url)
                await random_delay(2.0, 4.0)

                # Dismiss modal if present
                await self._dismiss_modal(session.page)

                await human_scroll(session.page, scrolls=3)
                await random_delay(1.0, 2.0)

                # Click job listings
                job_cards = await session.page.query_selector_all(
                    "li.JobsList_jobListItem__wjTHv, "
                    "li[data-test='jobListing'], "
                    "div.job-listing"
                )
                for card in job_cards[:15]:
                    try:
                        await card.click()
                        await random_delay(1.0, 2.0)
                    except Exception:
                        continue

                result = await self._extract_page_html(session.page, page_num)
                yield result

                # Check for next page
                next_btn = await session.page.query_selector(
                    "button[data-test='pagination-next'], "
                    "li.pagination__next a"
                )
                if not next_btn:
                    logger.info("glassdoor.no_more_pages", pages_scraped=page_num)
                    break

                await random_delay(2.0, 5.0)

    async def _dismiss_modal(self, page) -> None:
        try:
            close_btn = await page.query_selector(
                "button.modal_closeIcon, "
                "button[aria-label='Close'], "
                "span.SVGInline.modal_closeIcon"
            )
            if close_btn:
                await close_btn.click()
                await random_delay(0.5, 1.0)
        except Exception:
            pass
