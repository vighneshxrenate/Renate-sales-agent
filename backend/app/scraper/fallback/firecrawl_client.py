import aiohttp
import structlog

from app.config import settings

logger = structlog.get_logger()

FIRECRAWL_BASE = "https://api.firecrawl.dev/v1"


class FirecrawlClient:
    def __init__(self) -> None:
        self._api_key = settings.firecrawl_api_key

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def scrape_url(self, url: str, formats: list[str] | None = None) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {"url": url}
        if formats:
            payload["formats"] = formats
        else:
            payload["formats"] = ["html", "markdown"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FIRECRAWL_BASE}/scrape",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Firecrawl failed ({resp.status}): {body}")

                data = await resp.json()

        result = data.get("data", {})
        html = result.get("html", "")
        if not html:
            html = result.get("markdown", "")

        logger.info("firecrawl_scraped", url=url, length=len(html))
        return html
