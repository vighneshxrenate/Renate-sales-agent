import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
FIRECRAWL_CRAWL_URL = "https://api.firecrawl.dev/v1/crawl"


class FirecrawlClient:
    def __init__(self):
        self._api_key = settings.firecrawl_api_key
        self._client = httpx.AsyncClient(
            timeout=120,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) if self._api_key else None

    async def scrape_url(self, url: str, formats: list[str] | None = None) -> dict | None:
        if not self._client:
            logger.warning("firecrawl.no_api_key")
            return None

        try:
            payload = {"url": url}
            if formats:
                payload["formats"] = formats
            else:
                payload["formats"] = ["html", "markdown"]

            resp = await self._client.post(FIRECRAWL_SCRAPE_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                logger.info("firecrawl.scrape_success", url=url)
                return data.get("data")
            else:
                logger.warning("firecrawl.scrape_failed", url=url, error=data.get("error"))
                return None

        except Exception:
            logger.exception("firecrawl.scrape_error", url=url)
            return None

    async def crawl_site(
        self, url: str, max_pages: int = 10, include_paths: list[str] | None = None
    ) -> list[dict]:
        if not self._client:
            logger.warning("firecrawl.no_api_key")
            return []

        try:
            payload: dict = {
                "url": url,
                "limit": max_pages,
                "scrapeOptions": {"formats": ["html", "markdown"]},
            }
            if include_paths:
                payload["includePaths"] = include_paths

            resp = await self._client.post(FIRECRAWL_CRAWL_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("success"):
                results = data.get("data", [])
                logger.info("firecrawl.crawl_success", url=url, pages=len(results))
                return results
            else:
                logger.warning("firecrawl.crawl_failed", url=url)
                return []

        except Exception:
            logger.exception("firecrawl.crawl_error", url=url)
            return []

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
