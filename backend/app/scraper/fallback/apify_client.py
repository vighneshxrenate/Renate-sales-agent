import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

APIFY_RUN_URL = "https://api.apify.com/v2/acts/{actor_id}/runs"
APIFY_DATASET_URL = "https://api.apify.com/v2/datasets/{dataset_id}/items"

# Common Apify actors for job scraping
ACTORS = {
    "linkedin": "curious_coder~linkedin-jobs-scraper",
    "indeed": "misceres~indeed-scraper",
    "naukri": "epctex~naukri-scraper",
    "glassdoor": "epctex~glassdoor-scraper",
    "google_jobs": "lhotanok~google-jobs-scraper",
}


class ApifyClient:
    def __init__(self):
        self._api_key = settings.apify_api_key
        self._client = httpx.AsyncClient(
            timeout=120,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) if self._api_key else None

    async def scrape(
        self, source: str, keywords: str, location: str | None, max_results: int = 50
    ) -> list[dict]:
        if not self._client:
            logger.warning("apify.no_api_key")
            return []

        actor_id = ACTORS.get(source)
        if not actor_id:
            logger.warning("apify.no_actor", source=source)
            return []

        try:
            run_input = self._build_input(source, keywords, location, max_results)
            logger.info("apify.starting_run", actor=actor_id, source=source)

            resp = await self._client.post(
                APIFY_RUN_URL.format(actor_id=actor_id),
                json=run_input,
                params={"waitForFinish": 300},
            )
            resp.raise_for_status()
            run_data = resp.json()

            dataset_id = run_data["data"]["defaultDatasetId"]
            items_resp = await self._client.get(
                APIFY_DATASET_URL.format(dataset_id=dataset_id),
                params={"limit": max_results},
            )
            items_resp.raise_for_status()

            items = items_resp.json()
            logger.info("apify.completed", source=source, results=len(items))
            return items

        except Exception:
            logger.exception("apify.failed", source=source)
            return []

    def _build_input(
        self, source: str, keywords: str, location: str | None, max_results: int
    ) -> dict:
        loc = location or "India"

        if source == "linkedin":
            return {
                "searchUrl": f"https://www.linkedin.com/jobs/search/?keywords={keywords}&location={loc}",
                "maxItems": max_results,
            }
        elif source == "indeed":
            return {
                "query": keywords,
                "location": loc,
                "maxItems": max_results,
                "country": "IN" if "india" in loc.lower() else "US",
            }
        elif source == "naukri":
            return {
                "keyword": keywords,
                "location": loc,
                "maxItems": max_results,
            }
        elif source == "google_jobs":
            return {
                "queries": [f"{keywords} in {loc}"],
                "maxPagesPerQuery": max_results // 10,
            }
        return {"query": keywords, "location": loc, "maxItems": max_results}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
