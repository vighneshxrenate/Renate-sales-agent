import asyncio
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

import structlog

from app.models.scrape_job import ScrapeJob
from app.scraper.base import AbstractScraper, ScraperResult, register_scraper
from app.scraper.browser_pool import BrowserPool
from app.scraper.human_behavior import source_delay
from app.scraper.proxy_pool import ProxyPool
from app.services.ai_extraction import ExtractedLead

logger = structlog.get_logger()

MAX_PAGES_PER_SESSION = 15


def _parse_job(job: dict, source_url: str) -> ExtractedLead:
    placeholders = {p["type"]: p["label"] for p in job.get("placeholders", [])}
    experience = placeholders.get("experience", "")
    salary = placeholders.get("salary", "")
    location = placeholders.get("location", "")

    ambition = job.get("ambitionBoxData", {})
    rating = ambition.get("AggregateRating", "")
    review_count = ambition.get("ReviewsCount", "")
    description_parts = []
    if rating:
        description_parts.append(f"Rating: {rating}")
    if review_count:
        description_parts.append(f"Reviews: {review_count}")
    if job.get("jobDescription"):
        description_parts.append(job["jobDescription"][:300])

    jd_url = job.get("jdURL", "")
    if jd_url and not jd_url.startswith("http"):
        jd_url = f"https://www.naukri.com{jd_url}"

    return ExtractedLead(
        company_name=job.get("companyName", "Unknown"),
        source="naukri",
        source_url=source_url,
        location=location or None,
        website=None,
        industry=None,
        company_size=None,
        description="; ".join(description_parts) if description_parts else None,
        confidence_score=0.9,
        emails=[],
        phones=[],
        positions=[{
            "title": job.get("title", ""),
            "department": None,
            "location": location,
            "job_type": "Walk-in" if job.get("walkinJob") else "Full-time",
            "experience_level": experience,
            "salary_range": salary if salary and salary != "Not disclosed" else None,
            "source_url": jd_url,
            "raw_text": job.get("tagsAndSkills", ""),
        }],
    )


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
        keywords = (job.keywords or "jobs").replace(" ", "-")
        location = (job.location_filter or "india").replace(" ", "-").lower()
        max_pages = min(job.total_pages or 5, MAX_PAGES_PER_SESSION)

        proxy = proxy_pool.get_proxy(source="naukri")
        proxy_dict = proxy.to_playwright() if proxy else None
        ctx = await browser_pool.acquire(stealth_level="full", proxy=proxy_dict)

        try:
            page = await ctx.context.new_page()

            api_responses: list[dict] = []

            async def capture_response(response):
                if "jobapi/v3/search" in response.url:
                    try:
                        data = await response.json()
                        api_responses.append(data)
                    except Exception:
                        pass

            page.on("response", capture_response)

            for page_num in range(1, max_pages + 1):
                api_responses.clear()

                url = f"https://www.naukri.com/{quote_plus(keywords)}-jobs-in-{quote_plus(location)}"
                if page_num > 1:
                    url += f"-{page_num}"

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Wait for the API call to complete
                for _ in range(20):
                    if api_responses:
                        break
                    await asyncio.sleep(0.5)

                if not api_responses:
                    logger.warning("naukri_no_api_response", page=page_num, url=url)
                    continue

                data = api_responses[0]
                jobs_list = data.get("jobDetails", [])
                total = data.get("noOfJobs", 0)
                logger.info("naukri_page_scraped", page=page_num, jobs=len(jobs_list), total=total)

                leads = [_parse_job(j, url) for j in jobs_list if j.get("companyName")]

                yield ScraperResult(
                    raw_html="",
                    url=url,
                    source="naukri",
                    page_number=page_num,
                    structured_leads=leads,
                )

                if page_num < max_pages:
                    await source_delay("naukri")

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
