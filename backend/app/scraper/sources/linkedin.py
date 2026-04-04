import uuid as uuid_mod
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.human_behavior import human_scroll, random_delay, random_mouse_move, source_delay
from app.scraper.proxy_pool import ProxyPool
from app.services.ai_extraction import ExtractedLead

logger = structlog.get_logger()

JS_EXTRACT_CARDS = """() => {
    const cards = document.querySelectorAll(".base-card, .job-search-card, [data-entity-urn]");
    return Array.from(cards).map(card => {
        const title = card.querySelector(".base-search-card__title, h3");
        const company = card.querySelector(".base-search-card__subtitle, h4");
        const location = card.querySelector(".job-search-card__location");
        const link = card.querySelector("a");
        const posted = card.querySelector("time");
        return {
            title: title ? title.innerText.trim() : null,
            company: company ? company.innerText.trim() : null,
            location: location ? location.innerText.trim() : null,
            url: link ? link.href : null,
            posted: posted ? posted.innerText.trim() : null,
        };
    }).filter(j => j.title && j.company);
}"""


def _parse_card(card: dict, page_url: str) -> ExtractedLead:
    jd_url = card.get("url") or ""
    if jd_url and not jd_url.startswith("http"):
        jd_url = f"https://www.linkedin.com{jd_url}"

    return ExtractedLead(
        company_name=card["company"],
        source="linkedin",
        source_url=page_url,
        location=card.get("location"),
        website=None,
        industry=None,
        company_size=None,
        description=None,
        confidence_score=0.85,
        emails=[],
        phones=[],
        positions=[{
            "title": card["title"],
            "department": None,
            "location": card.get("location"),
            "job_type": None,
            "experience_level": None,
            "salary_range": None,
            "source_url": jd_url,
            "raw_text": card.get("posted", ""),
        }],
    )


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
        keywords = quote_plus(job.keywords or "jobs")
        location = quote_plus(job.location_filter or "India")
        max_pages = job.total_pages or 5

        session_id = str(uuid_mod.uuid4())[:8]
        proxy = proxy_pool.get_proxy(source="linkedin", sticky_session=session_id)
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="full", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}"

            for page_num in range(1, max_pages + 1):
                start = (page_num - 1) * 25
                url = f"{search_url}&start={start}" if start > 0 else search_url

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                content = await page.content()
                if "authwall" in content.lower():
                    logger.warning("linkedin_authwall", page=page_num)
                    break

                cards = await page.evaluate(JS_EXTRACT_CARDS)
                logger.info("linkedin_page_scraped", page=page_num, jobs=len(cards))

                if not cards:
                    logger.info("linkedin_no_more_results", page=page_num)
                    break

                leads = [_parse_card(c, url) for c in cards]

                yield ScraperResult(
                    raw_html="",
                    url=url,
                    source="linkedin",
                    page_number=page_num,
                    structured_leads=leads,
                )

                if page_num < max_pages:
                    await human_scroll(page, scrolls=2)
                    await source_delay("linkedin")

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
